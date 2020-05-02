# -*- coding: utf-8 -*-
# Copyright (c) 2019, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
import frappe.defaults
from frappe import _
from frappe.utils import cstr, cint, flt, comma_or, getdate, nowdate, formatdate, format_time
from erpnext.stock.utils import get_incoming_rate
from erpnext.stock.stock_ledger import get_previous_sle, NegativeStockError, get_valuation_rate
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.stock.get_item_details import get_bin_details, get_conversion_factor, get_default_cost_center
from erpnext.stock.doctype.batch.batch import get_batch_no, set_batch_nos, get_batch_qty
import json

from erpnext.controllers.stock_controller import StockController
from six import string_types

form_grid_templates = {
	"items": "templates/form_grid/stock_entry_grid.html"
}

class MaterialTransferInstruction(StockController):
	def onload(self):
		for item in self.get("items"):
			item.update(get_bin_details(item.item_code, item.s_warehouse))

	def validate(self):
		self.pro_doc = frappe._dict()
		if self.work_order:
			self.pro_doc = frappe.get_doc('Work Order', self.work_order)

		self.validate_posting_time()
		self.validate_item()
		self.set_transfer_qty()
		self.validate_uom_is_integer("uom", "qty")
		self.validate_uom_is_integer("stock_uom", "transfer_qty")
		self.validate_warehouse()
		self.validate_batch()
		if not self.from_bom:
			self.fg_completed_qty = 0.0

		if not self._action == 'submit':
			set_batch_nos(self, 's_warehouse')
			self.get_batch_details()

		self.set_incoming_rate()
		self.set_actual_qty()
		self.calculate_rate_and_amount(update_finished_item_rate=False)

	def on_submit(self):
		self.update_work_order()
		self.batch_validation()

	def on_cancel(self):
		self.check_stock_entries()
		self.update_work_order()

	def get_batch_details(self):
		batch_fields = ['lot_no', 'packaging_material', 'batch_yield', 'packing_size', 'concentration']
		for row in self.get('items'):
			if row.batch_no:
				batch_details = frappe.db.get_value("Batch", row.batch_no, batch_fields, as_dict=1)
				for field in batch_fields:
					row.set(field, batch_details[field])

	def update_work_order(self):
		if self.work_order:
			pro_doc = frappe.get_doc("Work Order", self.work_order)

			if self._action == 'submit':
				transferred_qty = flt(pro_doc.material_transferred_for_instruction) + flt(self.fg_completed_qty)
			elif self._action == 'cancel':
				transferred_qty = flt(pro_doc.material_transferred_for_instruction) - flt(self.fg_completed_qty)

			# if transferred_qty > round(pro_doc.qty, 2):
			# 	frappe.throw(_("Cannot Transfer more qty than Qty to Manufacture for Work Order {}".format(self.work_order)))

			pro_doc.material_transferred_for_instruction = transferred_qty
			status = "Not Started"
			if pro_doc.material_transferred_for_instruction:
				status = "In Process"

			pro_doc.db_set('status', status)
			pro_doc.save()
			frappe.db.commit()

	def check_stock_entries(self):
		stock_entries = frappe.get_list("Stock Entry", filters={
				'work_order': self.work_order,
				'docstatus': ['!=', '2']
			})

		if stock_entries:
			frappe.throw(_("Please delete Stock Entries in order to cancel this document."))

	def set_transfer_qty(self):
		for item in self.get("items"):
			if not flt(item.qty):
				frappe.throw(_("Row {0}: Qty is mandatory").format(item.idx))
			if not flt(item.conversion_factor):
				frappe.throw(_("Row {0}: UOM Conversion Factor is mandatory").format(item.idx))
			item.transfer_qty = flt(flt(item.qty) * flt(item.conversion_factor),
				self.precision("transfer_qty", item))

	def validate_item(self):
		stock_items = self.get_stock_items()
		serialized_items = self.get_serialized_items()
		for item in self.get("items"):
			if item.item_code not in stock_items:
				frappe.throw(_("{0} is not a stock Item").format(item.item_code))

			item_details = self.get_item_details(frappe._dict(
				{"item_code": item.item_code, "company": self.company,
				 "uom": item.uom, 's_warehouse': item.s_warehouse}),
				for_update=True)

			for f in ("uom", "stock_uom", "description", "item_name", "conversion_factor"):
					if f in ["stock_uom", "conversion_factor"] or not item.get(f):
						item.set(f, item_details.get(f))

			if not item.transfer_qty and item.qty:
				item.transfer_qty = item.qty * item.conversion_factor

			if (not item.serial_no and item.item_code in serialized_items):
				frappe.throw(_("Row #{0}: Please specify Serial No for Item {1}").format(item.idx, item.item_code),
					frappe.MandatoryError)

	def validate_warehouse(self):
		for d in self.get('items'):
			if not d.s_warehouse:
				if self.from_warehouse:
					d.s_warehouse = self.from_warehouse
				else:
					frappe.throw(_("Source warehouse is mandatory for row {0}").format(d.idx))

	def validate_batch(self):
		for item in self.get("items"):
			if item.batch_no:
				expiry_date = frappe.db.get_value("Batch", item.batch_no, "expiry_date")
				if expiry_date:
					if getdate(self.posting_date) > getdate(expiry_date):
						frappe.throw(_("Batch {0} of Item {1} has expired.").format(item.batch_no, item.item_code))
						
	def batch_validation(self):
		for item in self.get("items"):
			has_batch_no = frappe.db.get_value("Item",item.item_code,'has_batch_no')
			if has_batch_no and not item.batch_no:
				frappe.throw(_("Row: {} Please select the batch for item {}").format(item.idx, item.item_code))

	def set_incoming_rate(self):
		for d in self.items:
			if d.s_warehouse:
				args = self.get_args_for_incoming_rate(d)
				d.basic_rate = get_incoming_rate(args)

	def get_args_for_incoming_rate(self, item):
		return frappe._dict({
			"item_code": item.item_code,
			"warehouse": item.s_warehouse,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"qty": item.s_warehouse and -1*flt(item.transfer_qty) or flt(item.transfer_qty),
			"serial_no": item.serial_no,
			"voucher_type": self.doctype,
			"voucher_no": item.name,
			"company": self.company,
			"batch_no": item.batch_no,
		})

	def set_actual_qty(self):
		allow_negative_stock = cint(frappe.db.get_value("Stock Settings", None, "allow_negative_stock"))

		for d in self.get('items'):
			previous_sle = get_previous_sle({
				"item_code": d.item_code,
				"warehouse": d.s_warehouse,
				"posting_date": self.posting_date,
				"posting_time": self.posting_time
			})

			# get actual stock at source warehouse
			d.actual_qty = previous_sle.get("qty_after_transaction") or 0

			# validate qty during submit
			if d.docstatus==1 and d.s_warehouse and not allow_negative_stock and flt(d.actual_qty, d.precision("actual_qty")) < flt(d.transfer_qty, d.precision("actual_qty")):
				frappe.throw(_("Row {0}: Qty not available for {4} in warehouse {1} at posting time of the entry ({2} {3})").format(d.idx,
					frappe.bold(d.s_warehouse), formatdate(self.posting_date),
					format_time(self.posting_time), frappe.bold(d.item_code))
					+ '<br><br>' + _("Available qty is {0}, you need {1}").format(frappe.bold(d.actual_qty),
						frappe.bold(d.transfer_qty)),
					NegativeStockError, title=_('Insufficient Stock'))

	def calculate_rate_and_amount(self, force=False, update_finished_item_rate=True):
		self.set_basic_rate(force, update_finished_item_rate)
		# self.distribute_additional_costs()
		self.update_valuation_rate()
		# self.set_total_incoming_outgoing_value()
		self.set_total_amount()

	def set_basic_rate(self, force=False, update_finished_item_rate=True):
		"""get stock and incoming rate on posting date"""
		raw_material_cost = 0.0
		scrap_material_cost = 0.0
		fg_basic_rate = 0.0

		for d in self.get('items'):
			# if d.t_warehouse: fg_basic_rate = flt(d.basic_rate)
			args = self.get_args_for_incoming_rate(d)

			# get basic rate
			if not d.bom_no:
				if (not flt(d.basic_rate)) or d.s_warehouse or force:
					basic_rate = flt(get_incoming_rate(args), self.precision("basic_rate", d))
					if basic_rate > 0:
						d.basic_rate = basic_rate

				d.basic_amount = flt(flt(d.transfer_qty) * flt(d.basic_rate), d.precision("basic_amount"))

	def update_valuation_rate(self):
		for d in self.get("items"):
			if d.transfer_qty:
				d.amount = flt(d.basic_amount, d.precision("amount"))
				d.valuation_rate = flt(d.basic_rate), d.precision("valuation_rate")

	def set_total_amount(self):
		self.total_amount = sum([flt(item.amount) for item in self.get("items")])

	def get_item_details(self, args=None, for_update=False):
		item = frappe.db.sql("""select i.name, i.stock_uom, i.description, i.image, i.item_name, i.item_group,
				i.has_batch_no, i.sample_quantity, i.has_serial_no,
				id.expense_account, id.buying_cost_center
			from `tabItem` i LEFT JOIN `tabItem Default` id ON i.name=id.parent and id.company=%s
			where i.name=%s
				and i.disabled=0
				and (i.end_of_life is null or i.end_of_life='0000-00-00' or i.end_of_life > %s)""",
			(self.company, args.get('item_code'), nowdate()), as_dict = 1)

		if not item:
			frappe.throw(_("Item {0} is not active or end of life has been reached").format(args.get("item_code")))

		item = item[0]
		item_group_defaults = get_item_group_defaults(item.name, self.company)

		ret = frappe._dict({
			'uom'			      	: item.stock_uom,
			'stock_uom'				: item.stock_uom,
			'description'		  	: item.description,
			'image'					: item.image,
			'item_name' 		  	: item.item_name,
			'cost_center'			: item.get('buying_cost_center'),
			'qty'					: args.get("qty"),
			'transfer_qty'			: args.get('qty'),
			'conversion_factor'		: 1,
			'batch_no'				: '',
			'actual_qty'			: 0,
			'basic_rate'			: 0,
			'serial_no'				: '',
			'has_serial_no'			: item.has_serial_no,
			'has_batch_no'			: item.has_batch_no,
			'sample_quantity'		: item.sample_quantity
		})

		# update uom
		if args.get("uom") and for_update:
			ret.update(get_uom_details(args.get('item_code'), args.get('uom'), args.get('qty')))

		args['posting_date'] = self.posting_date
		args['posting_time'] = self.posting_time

		stock_and_rate = get_warehouse_details(args) if args.get('warehouse') else {}
		ret.update(stock_and_rate)

		# automatically select batch for outgoing item
		if (args.get('s_warehouse', None) and args.get('qty') and
			ret.get('has_batch_no') and not args.get('batch_no')):
			args.batch_no = get_batch_no(args['item_code'], args['s_warehouse'], args['qty'])

		return ret

	def get_items(self):
		self.set('items', [])
		# self.validate_work_order()

		if not self.posting_date or not self.posting_time:
			frappe.throw(_("Posting date and posting time is mandatory"))

		self.set_work_order_details()

		if self.bom_no:
			if self.work_order:
				item_dict = self.get_pending_raw_materials()
				self.add_to_stock_entry_detail(item_dict)

			elif self.work_order and \
				frappe.db.get_single_value("Manufacturing Settings", "backflush_raw_materials_based_on")== "Material Transferred for Manufacture":
				self.get_transfered_raw_materials()

			else:
				if not self.fg_completed_qty:
					frappe.throw(_("Manufacturing Quantity is mandatory"))

				item_dict = self.get_bom_raw_materials(self.fg_completed_qty)
				self.add_to_stock_entry_detail(item_dict)

		self.set_actual_qty()
		self.calculate_rate_and_amount()

	def set_work_order_details(self):
		if not getattr(self, "pro_doc", None):
			self.pro_doc = frappe._dict()

		if self.work_order:
			# common validations
			if not self.pro_doc:
				self.pro_doc = frappe.get_doc('Work Order', self.work_order)

			if self.pro_doc:
				self.bom_no = self.pro_doc.bom_no
				self.production_item = self.pro_doc.production_item
			else:
				# invalid Work Order
				self.work_order = None

	def get_pending_raw_materials(self):
		"""
			issue (item quantity) that is pending to issue or desire to transfer,
			whichever is less
		"""
		item_dict = self.get_pro_order_required_items()
		max_qty = flt(self.pro_doc.qty)
		for item, item_details in item_dict.items():
			pending_to_issue = flt(item_details.required_qty) - flt(item_details.transferred_qty)
			desire_to_transfer = flt(self.fg_completed_qty) * flt(item_details.required_qty) / max_qty

			if desire_to_transfer <= pending_to_issue:
				item_dict[item]["qty"] = desire_to_transfer
			elif pending_to_issue > 0:
				item_dict[item]["qty"] = pending_to_issue
			else:
				item_dict[item]["qty"] = 0

		# delete items with 0 qty
		for item in item_dict.keys():
			if not item_dict[item]["qty"]:
				del item_dict[item]

		# show some message
		if not len(item_dict):
			frappe.msgprint(_("""All items have already been transferred for this Work Order."""))

		return item_dict

	def get_pro_order_required_items(self):
		item_dict = frappe._dict()
		pro_order = frappe.get_doc("Work Order", self.work_order)

		for d in pro_order.get("required_items"):
			if flt(d.required_qty) > flt(d.transferred_qty):
				item_row = d.as_dict()
				if d.source_warehouse and not frappe.db.get_value("Warehouse", d.source_warehouse, "is_group"):
					item_row["from_warehouse"] = d.source_warehouse
				item_dict.setdefault(d.item_code, item_row)

		return item_dict

	def add_to_stock_entry_detail(self, item_dict, bom_no=None):
		for d in item_dict:
			stock_uom = item_dict[d].get("stock_uom") or frappe.db.get_value("Item", d, "stock_uom")

			se_child = self.append('items')
			se_child.s_warehouse = item_dict[d].get("from_warehouse")
			se_child.item_code = cstr(d)
			se_child.item_name = item_dict[d]["item_name"]
			se_child.description = item_dict[d]["description"]
			se_child.uom = stock_uom
			se_child.stock_uom = stock_uom
			se_child.qty = flt(item_dict[d]["qty"], se_child.precision("qty"))
			
			if item_dict[d].get("idx"):
				se_child.idx = item_dict[d].get("idx")

			if se_child.s_warehouse==None:
				se_child.s_warehouse = self.from_warehouse

			# in stock uom
			se_child.transfer_qty = flt(item_dict[d]["qty"], se_child.precision("qty"))
			se_child.conversion_factor = 1.00

			# to be assigned for finished item
			se_child.bom_no = bom_no

	def get_transfered_raw_materials(self):
		transferred_materials = frappe.db.sql("""
			select
				item_name, original_item, item_code, sum(qty) as qty, sed.t_warehouse as warehouse,
				description, stock_uom, expense_account, cost_center
			from `tabStock Entry` se,`tabStock Entry Detail` sed
			where
				se.name = sed.parent and se.docstatus=1 and se.purpose='Material Transfer for Manufacture'
				and se.work_order= %s and ifnull(sed.t_warehouse, '') != ''
			group by sed.item_code, sed.t_warehouse
		""", self.work_order, as_dict=1)

		materials_already_backflushed = frappe.db.sql("""
			select
				item_code, sed.s_warehouse as warehouse, sum(qty) as qty
			from
				`tabStock Entry` se, `tabStock Entry Detail` sed
			where
				se.name = sed.parent and se.docstatus=1
				and (se.purpose='Manufacture' or se.purpose='Material Consumption for Manufacture')
				and se.work_order= %s and ifnull(sed.s_warehouse, '') != ''
			group by sed.item_code, sed.s_warehouse
		""", self.work_order, as_dict=1)

		backflushed_materials= {}
		for d in materials_already_backflushed:
			backflushed_materials.setdefault(d.item_code,[]).append({d.warehouse: d.qty})

		po_qty = frappe.db.sql("""select qty, produced_qty, material_transferred_for_manufacturing from
			`tabWork Order` where name=%s""", self.work_order, as_dict=1)[0]

		manufacturing_qty = flt(po_qty.qty)
		produced_qty = flt(po_qty.produced_qty)
		trans_qty = flt(po_qty.material_transferred_for_manufacturing)

		for item in transferred_materials:
			qty= item.qty

			if trans_qty and manufacturing_qty > (produced_qty + flt(self.fg_completed_qty)):
				qty = (qty/trans_qty) * flt(self.fg_completed_qty)

			elif backflushed_materials.get(item.item_code):
				for d in backflushed_materials.get(item.item_code):
					if d.get(item.warehouse):
						qty-= d.get(item.warehouse)

			if qty > 0:
				self.add_to_stock_entry_detail({
					item.item_code: {
						"from_warehouse": item.warehouse,
						"to_warehouse": "",
						"qty": qty,
						"item_name": item.item_name,
						"description": item.description,
						"stock_uom": item.stock_uom
					}
				})

	def get_bom_raw_materials(self, qty):
		from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict

		# item dict = { item_code: {qty, description, stock_uom} }
		item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=qty,
			fetch_exploded = self.use_multi_level_bom)

		for item in item_dict.values():
			# if source warehouse presents in BOM set from_warehouse as bom source_warehouse
			item.from_warehouse = self.from_warehouse or item.source_warehouse or item.default_warehouse
		return item_dict

@frappe.whitelist()
def get_work_order_details(work_order):
	work_order = frappe.get_doc("Work Order", work_order)
	pending_qty_to_produce = flt(work_order.qty) - flt(work_order.produced_qty)

	return {
		"from_bom": 1,
		"bom_no": work_order.bom_no,
		"use_multi_level_bom": work_order.use_multi_level_bom,
		"wip_warehouse": work_order.wip_warehouse,
		"fg_warehouse": work_order.fg_warehouse,
		"fg_completed_qty": pending_qty_to_produce,
		"additional_costs": get_additional_costs(work_order, fg_qty=pending_qty_to_produce)
	}

def get_additional_costs(work_order=None, bom_no=None, fg_qty=None):
	additional_costs = []
	operating_cost_per_unit = get_operating_cost_per_unit(work_order, bom_no)
	if operating_cost_per_unit:
		additional_costs.append({
			"description": "Operating Cost as per Work Order / BOM",
			"amount": operating_cost_per_unit * flt(fg_qty)
		})

	if work_order and work_order.additional_operating_cost and work_order.qty:
		additional_operating_cost_per_unit = \
			flt(work_order.additional_operating_cost) / flt(work_order.qty)

		additional_costs.append({
			"description": "Additional Operating Cost",
			"amount": additional_operating_cost_per_unit * flt(fg_qty),
			'expense_account': 'Spray Drying Cost - EG'
		})

	return additional_costs

def get_operating_cost_per_unit(work_order=None, bom_no=None):
	operating_cost_per_unit = 0
	if work_order:
		if not bom_no:
			bom_no = work_order.bom_no

		for d in work_order.get("operations"):
			if flt(d.completed_qty):
				operating_cost_per_unit += flt(d.actual_operating_cost) / flt(d.completed_qty)
			elif work_order.qty:
				operating_cost_per_unit += flt(d.planned_operating_cost) / flt(work_order.qty)

	# Get operating cost from BOM if not found in work_order.
	if not operating_cost_per_unit and bom_no:
		bom = frappe.db.get_value("BOM", bom_no, ["operating_cost", "quantity"], as_dict=1)
		if bom.quantity:
			operating_cost_per_unit = flt(bom.operating_cost) / flt(bom.quantity)

	return operating_cost_per_unit

@frappe.whitelist()
def get_uom_details(item_code, uom, qty):
	"""Returns dict `{"conversion_factor": [value], "transfer_qty": qty * [value]}`

	:param args: dict with `item_code`, `uom` and `qty`"""
	conversion_factor = get_conversion_factor(item_code, uom).get("conversion_factor")

	if not conversion_factor:
		frappe.msgprint(_("UOM coversion factor required for UOM: {0} in Item: {1}")
			.format(uom, item_code))
		ret = {'uom' : ''}
	else:
		ret = {
			'conversion_factor'		: flt(conversion_factor),
			'transfer_qty'			: flt(qty) * flt(conversion_factor)
		}
	return ret

@frappe.whitelist()
def get_warehouse_details(args):
	if isinstance(args, string_types):
		args = json.loads(args)

	args = frappe._dict(args)

	ret = {}
	if args.warehouse and args.item_code:
		args.update({
			"posting_date": args.posting_date,
			"posting_time": args.posting_time,
		})
		ret = {
			"actual_qty" : get_previous_sle(args).get("qty_after_transaction") or 0,
			"basic_rate" : get_incoming_rate(args)
		}
	return ret

@frappe.whitelist()
def make_material_transfer(work_order_id, qty=None):
	work_order = frappe.get_doc("Work Order", work_order_id)

	mti = frappe.new_doc("Material Transfer Instruction")
	mti.work_order = work_order_id
	mti.company = work_order.company
	mti.from_bom = 1
	mti.bom_no = work_order.bom_no
	mti.use_multi_level_bom = work_order.use_multi_level_bom
	mti.fg_completed_qty = qty or (flt(work_order.qty) - flt(work_order.produced_qty))

	mti.get_items()
	return mti.as_dict()


@frappe.whitelist()
def get_raw_materials(work_order):
	mti_data = frappe.db.sql("""select name
		from `tabMaterial Transfer Instruction`
		where docstatus = 1
			and work_order = %s """, work_order, as_dict = 1)

	if not mti_data:
		frappe.msgprint(_("No Material Transfer Instruction found!"))
		return

	transfer_data = []

	for mti in mti_data:
		mti_doc = frappe.get_doc("Material Transfer Instruction", mti.name)
		for row in mti_doc.items:
			transfer_dict = {}
			transfer_dict['item_code'] = row.item_code
			transfer_dict['item_name'] = row.item_name
			transfer_dict['description'] = row.description
			transfer_dict['uom'] = row.uom
			transfer_dict['stock_uom'] = row.stock_uom
			transfer_dict['qty'] = row.qty
			transfer_dict['batch_no'] = row.batch_no
			transfer_dict['transfer_qty'] = row.transfer_qty
			transfer_dict['conversion_factor'] = row.conversion_factor
			transfer_dict['s_warehouse'] = row.s_warehouse
			transfer_dict['bom_no'] = row.bom_no
			transfer_dict['lot_no'] = row.lot_no
			transfer_dict['packaging_material'] = row.packaging_material
			transfer_dict['packing_size'] = row.packing_size
			transfer_dict['batch_yield'] = row.batch_yield
			transfer_dict['concentration'] = row.concentration
			transfer_data.append(transfer_dict)

	return transfer_data
