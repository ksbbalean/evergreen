from __future__ import unicode_literals
import frappe
import json
from frappe.utils import flt, add_days, cint, nowdate, getdate
from frappe import _, sendmail, db
from erpnext.utilities.product import get_price
from frappe.model.mapper import get_mapped_doc
from frappe.desk.reportview import get_match_cond, get_filters_cond
from frappe.contacts.doctype.address.address import get_address_display, get_default_address
from frappe.contacts.doctype.contact.contact import get_contact_details, get_default_contact
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder
from frappe.utils.background_jobs import enqueue
from erpnext.selling.doctype.customer.customer import Customer
from erpnext.buying.doctype.supplier.supplier import Supplier
from erpnext.controllers.accounts_controller import AccountsController, get_payment_terms

import functools


@frappe.whitelist()
def si_on_submit(self, method):
	export_lic(self)
	create_igst_jv(self)

@frappe.whitelist()
def si_on_cancel(self, method):
	export_lic_cancel(self)
	cancel_igst_jv(self)

@frappe.whitelist()
def si_onload(self, method):
	override_payment_schedule()

@frappe.whitelist()
def pi_onload(self, method):
	override_payment_schedule()

def override_payment_schedule():
	AccountsController.set_payment_schedule = set_payment_schedule
	# validate_due_date = _validate_due_date

def set_payment_schedule(self):
	if self.doctype == 'Sales Invoice' and self.is_pos:
		self.payment_terms_template = ''
		return

	posting_date = self.get("bl_date") or self.get("bill_date") or self.get("posting_date") or self.get("transaction_date")
	date = self.get("due_date")
	due_date = posting_date or date
	grand_total = self.get("rounded_total") or self.grand_total
	if self.doctype in ("Sales Invoice", "Purchase Invoice"):
		grand_total = grand_total - flt(self.write_off_amount)

	if not self.get("payment_schedule"):
		if self.get("payment_terms_template"):
			data = get_payment_terms(self.payment_terms_template, posting_date, grand_total)
			for item in data:
				self.append("payment_schedule", item)
		else:
			data = dict(due_date=due_date, invoice_portion=100, payment_amount=grand_total)
			self.append("payment_schedule", data)
	else:
		for d in self.get("payment_schedule"):
			credit_days = cint(frappe.db.get_value("Payment Term", d.payment_term, 'credit_days'))
			credit_due_date = add_days(due_date, credit_days)
			d.due_date = credit_due_date
			self.due_date = credit_due_date
			if d.invoice_portion:
				d.payment_amount = grand_total * flt(d.invoice_portion) / 100

@frappe.whitelist()
def pi_on_submit(self, method):
	import_lic(self)

@frappe.whitelist()
def pi_on_update(self, method):
	if self.workflow_state == "Approved":
		generate_pi_hash(self)

def generate_pi_hash(self):
	hash_key = None
	while not hash_key:
		hash_key = frappe.generate_hash(length=5)
		if frappe.db.exists("Purchase Invoice", {'hash_key': hash_key}):
			hash_key = None

	self.db_set('hash_key', hash_key)

@frappe.whitelist()
def pi_on_cancel(self, method):
	import_lic_cancel(self)
	remove_hash_key(self)

def remove_hash_key(self):
	if self.hash_key:
		self.db_set('hash_key', None)

def export_lic(self):
	for row in self.items:
		if row.advance_authorisation_license:
			aal = frappe.get_doc("Advance Authorisation License", row.advance_authorisation_license)
			if self.currency != "INR":
				fob = flt(row.fob_value)/ flt(self.conversion_rate)
			else:
				fob = flt(row.fob_value)
			aal.append("exports", {
				"item_code": row.item_code,
				"item_name": row.item_name,
				"quantity": row.qty,
				"uom": row.uom,
				"fob_value" : fob,
				"currency" : self.currency,
				"shipping_bill_no": self.shipping_bill_number,
				"shipping_bill_date": self.shipping_bill_date,
				"port_of_loading" : self.port_of_loading,
				"port_of_discharge" : self.port_of_discharge,
				"sales_invoice" : self.name,
			})

			aal.total_export_qty = sum([flt(d.quantity) for d in aal.exports])
			aal.total_export_amount = sum([flt(d.fob_value) for d in aal.exports])
			aal.save()
	else:
		frappe.db.commit()

def export_lic_cancel(self):
	doc_list = list(set([row.advance_authorisation_license for row in self.items if row.advance_authorisation_license]))

	for doc_name in doc_list:
		doc = frappe.get_doc("Advance Authorisation License", doc_name)
		to_remove = []

		for row in doc.exports:
			if row.parent == doc_name and row.sales_invoice == self.name:
				to_remove.append(row)

		[doc.remove(row) for row in to_remove]
		doc.total_export_qty = sum([flt(d.quantity) for d in doc.exports])
		doc.total_export_amount = sum([flt(d.fob_value) for d in doc.exports])
		doc.save()
	else:
		frappe.db.commit()


def import_lic(self):
	for row in self.items:
		if row.advance_authorisation_license:
			aal = frappe.get_doc("Advance Authorisation License", row.advance_authorisation_license)
			if self.currency != "INR":
				cif = flt(row.cif_value)/ flt(self.conversion_rate)
			else:
				cif = flt(row.cif_value)
			aal.append("imports", {
				"item_code": row.item_code,
				"item_name": row.item_name,
				"quantity": row.qty,
				"uom": row.uom,
				"cif_value" : cif,
				"currency" : self.currency,
				"shipping_bill_no": self.shipping_bill,
				"shipping_bill_date": self.shipping_bill_date,
				"port_of_loading" : self.port_of_loading,
				"port_of_discharge" : self.port_of_discharge,
				"purchase_invoice" : self.name,
			})

			aal.total_import_qty = sum([flt(d.quantity) for d in aal.imports])
			aal.total_import_amount = sum([flt(d.cif_value) for d in aal.imports])
			aal.save()
	else:
		frappe.db.commit()

def import_lic_cancel(self):
	doc_list = list(set([row.advance_authorisation_license for row in self.items if row.advance_authorisation_license]))

	for doc_name in doc_list:
		doc = frappe.get_doc("Advance Authorisation License", doc_name)
		to_remove = []

		for row in doc.imports:
			if row.parent == doc_name and row.purchase_invoice == self.name:
				to_remove.append(row)

		[doc.remove(row) for row in to_remove]
		doc.total_import_qty = sum([flt(d.quantity) for d in doc.imports])
		doc.total_import_amount = sum([flt(d.cif_value) for d in doc.imports])
		doc.save()
	else:
		frappe.db.commit()

@frappe.whitelist()
def override_po_functions(self, method):
	WorkOrder.get_status = get_status
	WorkOrder.update_work_order_qty = update_work_order_qty

def get_status(self, status=None):

	'''Return the status based on stock entries against this work order'''
	if not status:
		status = self.status

	if self.docstatus==0:
		status = 'Draft'
	elif self.docstatus==1:
		if status != 'Stopped':
			stock_entries = frappe._dict(frappe.db.sql("""select purpose, sum(fg_completed_qty)
				from `tabStock Entry` where work_order=%s and docstatus=1
				group by purpose""", self.name))

			status = "Not Started"
			if stock_entries:
				status = "In Process"
				produced_qty = stock_entries.get("Manufacture")

				under_production = flt(frappe.db.get_value("Manufacturing Settings", None, "under_production_allowance_percentage"))
				allowed_qty = flt(self.qty) * (100 - under_production) / 100.0

				if flt(produced_qty) >= flt(allowed_qty):
					status = "Completed"
	else:
		status = 'Cancelled'

	return status

def update_work_order_qty(self):
	"""Update **Manufactured Qty** and **Material Transferred for Qty** in Work Order
		based on Stock Entry"""

	for purpose, fieldname in (("Manufacture", "produced_qty"),
		("Material Transfer for Manufacture", "material_transferred_for_manufacturing")):
		qty = flt(frappe.db.sql("""select sum(fg_completed_qty)
			from `tabStock Entry` where work_order=%s and docstatus=1
			and purpose=%s""", (self.name, purpose))[0][0])

		self.db_set(fieldname, qty)

@frappe.whitelist()
def stock_entry_before_save(self, method):
	get_based_on(self)
	cal_target_yield_cons(self)
	if self.purpose == 'Repack' and cint(self.from_ball_mill) != 1:
		self.get_stock_and_rate()

	
def get_based_on(self):
	if self.work_order:
		self.based_on = frappe.db.get_value("Work Order", self.work_order, 'based_on')

def cal_target_yield_cons(self):
	cal_yield = 0
	cons = 0
	tot_quan = 0
	item_arr = list()
	item_map = dict()

	if self.purpose == "Manufacture":
		for d in self.items:
			if d.item_code not in item_arr:
				item_map.setdefault(d.item_code, 0)
			
			item_map[d.item_code] += flt(d.qty)

		# Last row object
		last_row = self.items[-1]

		# Last row batch_yield
		batch_yield = last_row.batch_yield

		# List of item_code from items table
		items_list = [row.item_code for row in self.items]

		# Check if items list has "Vinyl Sulphone (V.S)" and no based_on value
		if not self.based_on and "Vinyl Sulphone (V.S)" in items_list:
			cal_yield = flt(last_row.qty / item_map["Vinyl Sulphone (V.S)"]) # Last row qty / sum of items of "Vinyl Sulphone (V.S)" from map variable

		# Check if items list has frm.doc.based_on value
		elif self.based_on in items_list:
			cal_yield = flt(last_row.qty / item_map[self.based_on]) # Last row qty / sum of items of based_on item from map variable

		# if self.bom_no:
		# 	bom_batch_yield = flt(frappe.db.get_value("BOM", self.bom_no, 'batch_yield'))
		# 	cons = flt(bom_batch_yield * 100) / flt(cal_yield)
		# 	last_row.concentration = cons

		last_row.batch_yield = flt(cal_yield) * (flt(last_row.concentration) / 100.0)


@frappe.whitelist()
def stock_entry_on_submit(self, method):
	update_po(self)

def update_po(self,ignore_permissions = True):
	if self.purpose in ["Material Transfer for Manufacture", "Manufacture"] and self.work_order:
		if self.purpose == 'Manufacture':
			po = frappe.get_doc("Work Order",self.work_order)
			update_po_volume(self, po)
			update_po_transfer_qty(self, po)
			update_po_items(self, po)

			last_item = self.items[-1]

			po.batch_yield = last_item.batch_yield
			po.concentration = last_item.concentration
			po.batch = last_item.get('batch_no')
			po.lot_no = last_item.lot_no
			po.valuation_rate = last_item.valuation_rate

			po.save()
			frappe.db.commit()

def update_po_volume(self, po, ignore_permissions = True):
	if not self.volume:
		frappe.throw(_("Please add volume before submitting the stock entry"))

	if self._action == 'submit':
		po.volume += self.volume
		self.volume_cost = flt(flt(self.volume) * flt(self.volume_rate))		
		po.volume_cost +=  self.volume_cost
		#self.save(ignore_permissions = True)
		po.save(ignore_permissions = True)

	elif self._action == 'cancel':
		po.volume -= self.volume
		po.volume_cost -= self.volume_cost
		po.save(ignore_permissions = True)

def update_po_transfer_qty(self, po):
	for d in po.required_items:
		se_items_date = frappe.db.sql('''select sum(qty), valuation_rate
			from `tabStock Entry` entry, `tabStock Entry Detail` detail
			where
				entry.work_order = %s
				and entry.purpose = "Manufacture"
				and entry.docstatus = 1
				and detail.parent = entry.name
				and detail.item_code = %s''', (po.name, d.item_code))[0]

		d.db_set('transferred_qty', flt(se_items_date[0]), update_modified = False)
		d.db_set('valuation_rate', flt(se_items_date[1]), update_modified = False)

def update_po_items(self,po):
	from erpnext.stock.utils import get_latest_stock_qty

	for row in self.items:
		if row.s_warehouse and not row.t_warehouse:
			item = [d.name for d in po.required_items if d.item_code == row.item_code]

			if not item:
				po.append('required_items', {
					'item_code': row.item_code,
					'item_name': row.item_name,
					'description': row.description,
					'source_warehouse': row.s_warehouse,
					'required_qty': row.qty,
					'transferred_qty': row.qty,
					'valuation_rate': row.valuation_rate,
					'available_qty_at_source_warehouse': get_latest_stock_qty(row.item_code, row.s_warehouse),
				})

	for child in po.required_items:
		child.db_update()

@frappe.whitelist()
def stock_entry_on_cancel(self, method):
	if self.work_order:
		pro_doc = frappe.get_doc("Work Order", self.work_order)
		set_po_status(self, pro_doc)
		update_po_volume(self, pro_doc)
		update_po_transfer_qty(self, pro_doc)

		pro_doc.save()
		frappe.db.commit()

def set_po_status(self, pro_doc):
	status = None
	if flt(pro_doc.material_transferred_for_instruction):
		status = "In Process"

	if status:
		pro_doc.db_set('status', status)

@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	def set_missing_values(source, target):
		for row in source.items:
			target.append("items", {
				"item_code": row.item_code,
				"item_name": row.item_name,
				"schedule_date": source.schedule_date,
				"item_group": row.item_group,
				"brand": row.brand,
				"image": row.image,
				"description": row.description,
				"uom": row.uom,
				"qty":row.qty
			})
	
	doclist = get_mapped_doc("Opportunity", source_name, {
			"Opportunity": {
				"doctype": "Request for Quotation",
				"field_map": {	
				}
			},
		}, target_doc, set_missing_values)
	return doclist

@frappe.whitelist()
def upadte_item_price(item, price_list, per_unit_price):
	if db.exists("Item Price",{"item_code":item,"price_list":price_list}):
		name = db.get_value("Item Price",{"item_code":item,"price_list":price_list},'name')
		db.set_value("Item Price",name,"price_list_rate", per_unit_price)
	else:
		item_price = frappe.new_doc("Item Price")
		item_price.price_list = price_list
		item_price.item_code = item
		item_price.price_list_rate = per_unit_price
		
		item_price.save()
	db.commit()
		
	return "Item Price Updated!"

@frappe.whitelist()	
def upadte_item_price_daily():
	data = db.sql("""
		select 
			item, per_unit_price , buying_price_list
		from
			`tabBOM` 
		where 
			docstatus < 2 
			and is_default = 1 """,as_dict =1)
			
	for row in data:
		upadte_item_price(row.item, row.buying_price_list, row.per_unit_price)
		
	return "Latest price updated in Price List."

@frappe.whitelist()
def bom_before_save(self, method):
	operating_cost = flt(self.volume_quantity * self.volume_rate)
	self.total_cost = self.raw_material_cost + self.total_operational_cost + operating_cost - self.scrap_material_cost 
	per_unit_price = flt(self.total_cost) / flt(self.quantity)
	self.operating_cost = operating_cost

	if self.per_unit_price != per_unit_price:
		self.per_unit_price  = per_unit_price
		

@frappe.whitelist()
def enqueue_update_cost():
	frappe.enqueue("evergreen.api.update_cost")
	frappe.msgprint(_("Queued for updating latest price in all Bill of Materials. It may take a few minutes."))

def update_cost():
	from erpnext.manufacturing.doctype.bom.bom import get_boms_in_bottom_up_order

	bom_list = get_boms_in_bottom_up_order()
	for bom in bom_list:
		bom_obj = frappe.get_doc("BOM", bom)
		bom_obj.update_cost(update_parent=False, from_child_bom=True)

		per_unit_price = flt(bom_obj.total_cost) / flt(bom_obj.quantity)

		if bom_obj.per_unit_price != per_unit_price:
			bom_obj.db_set('per_unit_price', per_unit_price)		
		
@frappe.whitelist()
def get_spare_price(item_code, price_list, customer_group="All Customer Groups", company="Evergreen Industries"):
	price = get_price(item_code, price_list, customer_group, company)
	
	if not price:
		price = frappe._dict({'price_list_rate': 0.0})

	return price

@frappe.whitelist()
def update_outward_sample(doc_name):
	
	outward = frappe.get_doc("Outward Sample", doc_name)

	total_qty = 0
	total_amount = 0
	
	for row in outward.details:
		if row.item_name:
			price = get_spare_price(row.item_name, outward.price_list or "Standard Buying")
			row.db_set('rate', price.price_list_rate)
			row.db_set('price_list_rate', price.price_list_rate)

		if row.batch_yield:
			bomyield = frappe.db.get_value("BOM",{'item': row.item_name},"batch_yield")
			if bomyield != 0:
				row.db_set('rate',(flt(row.price_list_rate)) * flt(bomyield) / row.batch_yield)
			else:
				row.db_set('rate',(flt(row.price_list_rate) * 2.2) / row.batch_yield)

		row.db_set('amount', flt(row.quantity) * flt(row.rate))

		total_qty += row.quantity
		total_amount += flt(row.amount)

	outward.db_set("total_qty", total_qty)
	outward.db_set("total_amount", total_amount)
	if total_qty == 0:
		outward.db_set("per_unit_price", 0)
	else:
		outward.db_set("per_unit_price", (total_amount / total_qty))
	outward.db_set("price_updated_on",nowdate())
	
	return "Price Updated"


@frappe.whitelist()
def get_custom_address(party=None, party_type="Customer", ignore_permissions=False):

	if not party:
		return {}

	if not frappe.db.exists(party_type, party):
		frappe.throw(_("{0}: {1} does not exists").format(party_type, party))

	return _get_custom_address(party, party_type, ignore_permissions)

def _get_custom_address(party=None, party_type="Customer", ignore_permissions=False):

	out = frappe._dict({
		party_type.lower(): party
	})

	party = out[party_type.lower()]

	if not ignore_permissions and not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted for {0}").format(party), frappe.PermissionError)

	party = frappe.get_doc(party_type, party)
	
	set_custom_address_details(out, party, party_type)
	return out

def set_custom_address_details(out, party, party_type):
	billing_address_field = "customer_address" if party_type == "Lead" \
		else party_type.lower() + "_address"
	out[billing_address_field] = get_custom_default_address(party_type, party.name)
	
	# address display
	out.address_display = get_custom_address_display(out[billing_address_field])

def get_custom_address_display(address_dict):
	if not address_dict:
		return

	if not isinstance(address_dict, dict):
		address_dict = frappe.db.get_value("Address", address_dict, "*", as_dict=True, cache=True) or {}

	name, template = get_custom_address_templates(address_dict)

	try:
		return frappe.render_template(template, address_dict)
	except TemplateSyntaxError:
		frappe.throw(_("There is an error in your Address Template {0}").format(name))

def get_custom_address_templates(address):
	result = frappe.db.get_value("Address Template", \
		{"country": address.get("country")}, ["name", "template"])

	if not result:
		result = frappe.db.get_value("Address Template", \
			{"is_default": 1}, ["name", "template"])

	if not result:
		frappe.throw(_("No default Address Template found. Please create a new one from Setup > Printing and Branding > Address Template."))
	else:
		return result

def get_custom_default_address(doctype, name, sort_key='is_primary_address'):
	'''Returns default Address name for the given doctype, name'''
	out = frappe.db.sql('''select
			parent, (select name from tabAddress a where a.name=dl.parent) as name,
			(select address_type from tabAddress a where a.name=dl.parent and a.address_type="Consignee-Custom") as address_type
			from
			`tabDynamic Link` dl
			where
			link_doctype=%s and
			link_name=%s and
			parenttype = "Address" and
			(select address_type from tabAddress a where a.name=dl.parent)="Consignee-Custom"
		'''.format(sort_key),(doctype, name))

	if out:
		return sorted(out, key = functools.cmp_to_key(lambda x,y: cmp(y[1], x[1])))[0][0]
	else:
		return None



@frappe.whitelist()
def get_party_details(party=None, party_type="Customer", ignore_permissions=True):

	if not party:
		return {}

	if not frappe.db.exists(party_type, party):
		frappe.throw(_("{0}: {1} does not exists").format(party_type, party))

	return _get_party_details(party, party_type, ignore_permissions)

def _get_party_details(party=None, party_type="Customer", ignore_permissions=True):

	out = frappe._dict({
		party_type.lower(): party
	})

	party = out[party_type.lower()]

	if not ignore_permissions and not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted for {0}").format(party), frappe.PermissionError)

	party = frappe.get_doc(party_type, party)
	
	set_address_details(out, party, party_type)
	set_contact_details(out, party, party_type)
	set_other_values(out, party, party_type)
	set_organisation_details(out, party, party_type)
	return out

def set_address_details(out, party, party_type):
	billing_address_field = "customer_address" if party_type == "Lead" \
		else party_type.lower() + "_address"
	out[billing_address_field] = get_default_address(party_type, party.name)
	
	# address display
	out.address_display = get_address_display(out[billing_address_field])


def set_contact_details(out, party, party_type):
	out.contact_person = get_default_contact(party_type, party.name)

	if not out.contact_person:
		out.update({
			"contact_person": None,
			"contact_display": None,
			"contact_email": None,
			"contact_mobile": None,
			"contact_phone": None,
			"contact_designation": None,
			"contact_department": None
		})
	else:
		out.update(get_contact_details(out.contact_person))

def set_other_values(out, party, party_type):
	# copy
	if party_type=="Customer":
		to_copy = ["customer_name", "customer_group", "territory", "language"]
	else:
		to_copy = ["supplier_name", "supplier_type", "language"]
	for f in to_copy:
		out[f] = party.get(f)
		
def set_organisation_details(out, party, party_type):

	organisation = None

	if party_type == 'Lead':
		organisation = frappe.db.get_value("Lead", {"name": party.name}, "company_name")
	elif party_type == 'Customer':
		organisation = frappe.db.get_value("Customer", {"name": party.name}, "customer_name")
	elif party_type == 'Supplier':
		organisation = frappe.db.get_value("Supplier", {"name": party.name}, "supplier_name")

	out.update({'party_name': organisation})


@frappe.whitelist()
def IP_before_save(self,method):
	fetch_item_group(self)

def fetch_item_group(self):
	item_group = frappe.db.get_value("Item", self.item_code, "item_group")
	("item_group", item_group)

@frappe.whitelist()
def get_items(customer):	
	where_clause = ''
	where_clause += customer and " parent = '%s' " % customer.replace("'", "\'") or ''
	
	return frappe.db.sql("""
		SELECT item_code FROM `tabCustomer Item` WHERE %s ORDER BY idx"""% where_clause, as_dict=1)


def new_item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	conditions = []

	return db.sql("""
		select tabItem.name, tabItem.item_customer_code, tabItem.item_group,
			if(length(tabItem.item_name) > 40, concat(substr(tabItem.item_name, 1, 40), "..."), item_name) as item_name,
			tabItem.item_group, if(length(tabItem.description) > 40, concat(substr(tabItem.description, 1, 40), "..."), description) as decription
		from tabItem
		where 
			tabItem.docstatus < 2
			and tabItem.has_variants=0
			and tabItem.disabled=0
			and (tabItem.end_of_life > %(today)s or ifnull(tabItem.end_of_life, '0000-00-00')='0000-00-00')
			and (tabItem.`{key}` LIKE %(txt)s
				or tabItem.item_name LIKE %(txt)s
				or tabItem.item_group LIKE %(txt)s
				or tabItem.item_customer_code LIKE %(txt)s
				or tabItem.barcode LIKE %(txt)s)
			{fcond} {mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, item_name), locate(%(_txt)s, item_name), 99999) 
		limit %(start)s, %(page_len)s """.format(
			key=searchfield,
			fcond=get_filters_cond(doctype, filters, conditions).replace('%', '%%'),
			mcond=get_match_cond(doctype).replace('%', '%%')),
			{
				"today": nowdate(),
				"txt": "%s%%" % txt,
				"_txt": txt.replace("%", ""),
				"start": start,
				"page_len": page_len
			}, as_dict=as_dict)

 # searches for customer
@frappe.whitelist(allow_guest = 1)
def new_customer_query(doctype, txt, searchfield, start, page_len, filters):
	conditions = []
	meta = frappe.get_meta("Customer")
	searchfields = meta.get_search_fields()
	searchfields = searchfields + [f for f in [searchfield or "name", "customer_name"] \
			if not f in searchfields]

	searchfields = " or ".join([field + " like %(txt)s" for field in searchfields])
	fields = ["name"]
	fields = ", ".join(fields)

	return frappe.db.sql("""select {fields} from `tabCustomer`
		where docstatus < 2
			and ({scond}) and disabled=0
			{fcond} {mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, customer_name), locate(%(_txt)s, customer_name), 99999),
			idx desc,
			name, customer_name
		limit %(start)s, %(page_len)s""".format(**{
			"fields": fields,
			"mcond": get_match_cond(doctype),
			"scond": searchfields,
			"fcond": get_filters_cond(doctype, filters, conditions).replace('%', '%%'),
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len
		})

# searches for supplier
@frappe.whitelist()
def new_supplier_query(doctype, txt, searchfield, start, page_len, filters):
	supp_master_name = frappe.defaults.get_user_default("supp_master_name")
	if supp_master_name == "Supplier Name":
		fields = ["name"]
	else:
		fields = ["name"]
	fields = ", ".join(fields)

	return frappe.db.sql("""select {field} from `tabSupplier`
		where docstatus < 2
			and ({key} like %(txt)s
				or supplier_name like %(txt)s) and disabled=0
			{mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, supplier_name), locate(%(_txt)s, supplier_name), 99999),
			idx desc,
			name, supplier_name
		limit %(start)s, %(page_len)s """.format(**{
			'field': fields,
			'key': searchfield,
			'mcond':get_match_cond(doctype)
		}), {
			'txt': "%%%s%%" % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len
		})

@frappe.whitelist()	
def sales_order_query(doctype, txt, searchfield, start, page_len, filters):
	conditions = []

	so_searchfield = frappe.get_meta("Sales Order").get_search_fields()
	so_searchfields = " or ".join(["so.`" + field + "` like %(txt)s" for field in so_searchfield])

	soi_searchfield = frappe.get_meta("Sales Order Item").get_search_fields()
	soi_searchfield += ["item_code"]
	soi_searchfields = " or ".join(["soi.`" + field + "` like %(txt)s" for field in soi_searchfield])

	searchfield = so_searchfields + " or " + soi_searchfields

	return frappe.db.sql("""select so.name, so.status, so.transaction_date, so.customer, soi.item_code
			from `tabSales Order` so
		RIGHT JOIN `tabSales Order Item` soi ON (so.name = soi.parent)
		where so.docstatus = 1
			and so.status != "Closed"
			and so.customer = %(customer)s
			and ({searchfield})
		order by
			if(locate(%(_txt)s, so.name), locate(%(_txt)s, so.name), 99999)
		limit %(start)s, %(page_len)s """.format(searchfield=searchfield), {
			'txt': '%%%s%%' % txt,
			'_txt': txt.replace("%", ""),
			'start': start,
			'page_len': page_len,
			'customer': filters.get('customer')
		})
		
@frappe.whitelist()
def get_customer_ref_code(item_code, customer):
	ref_code = db.get_value("Item Customer Detail", {'parent': item_code, 'customer_name': customer}, 'ref_code')
	return ref_code if ref_code else ''
	
@frappe.whitelist()
def customer_auto_name(self, method):
	if self.alias and self.customer_name != self.alias:
		self.name = self.alias

@frappe.whitelist()
def customer_override_after_rename(self, method, *args, **kwargs):
	Customer.after_rename = cust_after_rename

def cust_after_rename(self, olddn, newdn, merge=False):
	if frappe.defaults.get_global_default('cust_master_name') == 'Customer Name' and self.alias == self.customer_name:
		frappe.db.set(self, "customer_name", newdn)


@frappe.whitelist()
def supplier_auto_name(self, method):
	if self.alias and self.supplier_name != self.alias:
		self.name = self.alias

@frappe.whitelist()
def supplier_override_after_rename(self, method, *args, **kwargs):
	Supplier.after_rename = supp_after_rename

def supp_after_rename(self, olddn, newdn, merge=False):
	if frappe.defaults.get_global_default('supp_master_name') == 'Supplier Name' and self.alias == self.supplier_name:
		frappe.db.set(self, "supplier_name", newdn)

@frappe.whitelist()
def item_validate(self, method):
	fill_customer_code(self)

def fill_customer_code(self):
	""" Append all the customer codes and insert into "customer_code" field of item table """
	cust_code = []
	for d in self.get('customer_items'):
		cust_code.append(d.ref_code)
	self.customer_code = ""
	self.item_customer_code = ','.join(cust_code)

@frappe.whitelist()
def make_shipping_document(source_name, target_doc=None, ignore_permissions=False):
	doclist = get_mapped_doc("Sales Order", source_name, {
		"Sales Order": {
			"doctype": "Shipping Document",
			"field_map": {
				"per_billed": "per_billed",
				"delivery_status": "delivery_status",
				"per_delivered": "per_delivered",
				"advance_paid": "advance_paid",
				"base_rounding_adjustment": "base_rounding_adjustment",
				"ignore_pricing_rule": "ignore_pricing_rule",
				"other_charges_calculation": "other_charges_calculation",
				"party_account_currency": "party_account_currency",
				"transaction_date": "transaction_date",
				"delivery_date": "delivery_date",
				"payment_schedule": "payment_schedule",
				"rounding_adjustment": "rounding_adjustment",
			},
			"validation": {
				"docstatus": ["=", 1]
			}
		},
		"Sales Order Item": {
			"doctype": "Shipping Document Item",
			"field_map": {
				"name": "so_detail",
				"parent": "sales_order",
				"delivery_date": "delivery_date",
				"actual_qty": "actual_qty",
				"stock_qty": "stock_qty",
				"returned_qty": "returned_qty",
				"gross_profit": "gross_profit",
				"ordered_qty": "ordered_qty",
				"valuation_rate": "valuation_rate",
				"delivered_qty": "delivered_qty",
				"billed_amt": "billed_amt",
				"planned_qty": "planned_qty",
				"target_warehouse": "target_warehouse",
			},
		},
		"Sales Taxes and Charges": {
			"doctype": "Sales Taxes and Charges",
			"add_if_empty": True
		},
		"Packed Item": {
			"doctype": "Packed Item",
		}
	}, target_doc, ignore_permissions=ignore_permissions)

	return doclist
	
@frappe.whitelist()
def pr_on_submit(self,method):
	validate_po_num(self)

def validate_po_num(self):
	for row in self.items:
		if row.item_group in ['FINISHED DYES','Raw Material','SEMI FINISHED DYES'] and not row.purchase_order:
			frappe.throw(_("Purchase order is manadatory for Item <b>{0}</b> in row {1}").format(row.item_code,row.idx))
			
@frappe.whitelist()
def docs_before_naming(self, method):
	from erpnext.accounts.utils import get_fiscal_year

	date = self.get("transaction_date") or self.get("posting_date") or getdate()

	fy = get_fiscal_year(date)[0]
	fiscal = frappe.db.get_value("Fiscal Year", fy, 'fiscal')

	if fiscal:
		self.fiscal = fiscal
	else:
		fy_years = fy.split("-")
		fiscal = fy_years[0][2:] + fy_years[1][2:]
		self.fiscal = fiscal
	
@frappe.whitelist()
def dn_on_submit(self, method):
	update_sales_invoice(self)

@frappe.whitelist()
def dn_before_cancel(self, method):
	update_sales_invoice(self)

def update_sales_invoice(self):
	for row in self.items:
		if row.against_sales_invoice and row.si_detail:
			if self._action == 'submit':
				delivery_note = self.name
				dn_detail = row.name

			elif self._action == 'cancel':
				delivery_note = ''
				dn_detail = ''

			frappe.db.sql("""update `tabSales Invoice Item` 
				set dn_detail = %s, delivery_note = %s 
				where name = %s """, (dn_detail, delivery_note, row.si_detail))

def create_igst_jv(self):
	abbr = frappe.db.get_value("Company", self.company, 'abbr')
	
	if len(self.taxes):
		for row in self.taxes:
			if self.export_type == "With Payment of Tax" and self.currency != "INR" and 'IGST' in row.account_head:
				jv = frappe.new_doc("Journal Entry")
				jv.voucher_type = "Export IGST Entry"
				jv.posting_date = self.posting_date
				jv.company = self.company
				jv.cheque_no = self.invoice_no
				jv.cheque_date = self.posting_date
				jv.multi_currency = 1
				#jv.user_remark = "IGST Payable against" + self.name + " for " + self.customer
					
				jv.append("accounts", {
					"account": 'Sales - %s' % abbr,
					"cost_center": 'Main - %s' % abbr,
					"debit_in_account_currency": row.base_tax_amount
				})
				jv.append("accounts", {
					"account": self.debit_to,
					"cost_center": 'Main - %s' % abbr,
					"exchange_rate":  self.conversion_rate,
					"party_type": 'Customer',
					"party": self.customer,
					"reference_type": 'Sales Invoice',
					"reference_name": self.name,
					"credit_in_account_currency": row.tax_amount_after_discount_amount
				})
				jv.save(ignore_permissions=True)
				self.db_set('gst_jv', jv.name)
				jv.submit()
				frappe.db.commit()
	
def cancel_igst_jv(self):
	if self.gst_jv:
		jv = frappe.get_doc("Journal Entry", self.gst_jv)
		jv.cancel()
		self.db_set('gst_jv', '')
	frappe.db.commit()

@frappe.whitelist()
def jobwork_update():
	
	for jc in frappe.get_list("Jobwork Challan",filters={"docstatus": 1}):
		doc = frappe.get_doc("Jobwork Challan", jc.name)
		
		for row in doc.items:
			qty = flt(frappe.db.sql("""select sum(received_qty) from `tabJobwork Finish Item` where docstatus = 1 and job_work_item = %s """, row.name)[0][0])
			row.db_set('received_qty', qty)

		doc.update_status()

# @frappe.whitelist()
# def delivery_note_patch():
# 	data = frappe.db.sql("""
# 		select name from `tabDelivery Note` where docstatus = 1
# 		""", as_dict=1)
	
# 	for d in data:
# 		doc = frappe.get_doc("Delivery Note", d.name)

# 		print(doc.name)

# 		for row in doc.items:
# 			if row.against_sales_invoice:
# 				delivery_note = doc.name
# 				dn_detail = row.name

# 				frappe.db.sql("""update `tabSales Invoice Item` 
# 					set dn_detail = %s, delivery_note = %s 
# 					where name = %s """, (dn_detail, delivery_note, row.si_detail))

# 		# 		si_item_name = frappe.db.sql("select name from `tabSales Invoice Item` where parent = %s and item_code = %s", (row.against_sales_invoice, row.item_code))[0][0]
# 		# 		row.db_set('si_detail', si_item_name)
# 		# 		print(row.si_detail)
# 		# 		# print(si_item_name)

# 		# print("----------")

# 	return "Done"