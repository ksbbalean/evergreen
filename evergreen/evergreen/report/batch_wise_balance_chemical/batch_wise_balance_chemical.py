# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, cint, getdate

def execute(filters=None):
	if not filters: filters = {}

	float_precision = cint(frappe.db.get_default("float_precision")) or 3

	columns = get_columns(filters)
	item_map = get_item_details(filters)
	iwb_map = get_item_warehouse_batch_map(filters, float_precision)
	iwb_map_without_group = get_item_warehouse_batch_map_without_group(filters, float_precision)

	data = []
	for company in sorted(iwb_map):
		for item in sorted(iwb_map[company]):
			for wh in sorted(iwb_map[company][item]):
				for batch in sorted(iwb_map[company][item][wh]):
					qty_dict = iwb_map[company][item][wh][batch]
					qty_dict_without_group = iwb_map_without_group[company][item][wh][batch]
					if qty_dict.opening_qty or qty_dict.in_qty or qty_dict.out_qty or qty_dict.bal_qty:
						lot_no, packaging_material, packing_size_link, concentration, valuation_rate = frappe.db.get_value("Batch", batch, ["lot_no", "packaging_material","packing_size","concentration","valuation_rate"])
						packing_size_val = frappe.db.get_value("Packing Size",packing_size_link,'packing_size')
						if packing_size_val:
							packing_size = int(''.join(filter(lambda i: i.isdigit(), packing_size_val)))
						else:
							packing_size = 0
						# data.append([item, wh, batch, lot_no, concentration, packaging_material, packing_size
						# 	flt(qty_dict.bal_qty, float_precision),
						# 	 item_map[item]["stock_uom"]
						# ])

						if item_map[item]["maintain_as_is_stock"]:
							data.append({
								'item_code': item,
								'item_group': item_map[item]["item_group"],
								'warehouse': wh,
								'batch_no': batch,
								'lot_no': lot_no,
								'voucher_type': qty_dict_without_group.voucher_type,
								'voucher_no': qty_dict_without_group.voucher_no,
								'concentration': concentration,
								'packaging_material': packaging_material,
								'packing_size': packing_size,
								'company':qty_dict.company,
								'packages': flt(qty_dict.bal_qty/packing_size) if packing_size else 0,
								'bal_qty': flt(qty_dict.bal_qty*concentration/100, float_precision),
								'amount': flt((qty_dict.bal_qty*concentration/100) * flt(valuation_rate*100/concentration) , float_precision),
								'as_is_qty': flt(qty_dict.bal_qty, float_precision),
								'valuation_rate':flt(valuation_rate*100/concentration,float_precision),
								'uom': item_map[item]["stock_uom"],
								'party_type':qty_dict_without_group.party_type,
								'party':qty_dict_without_group.party,
							})
						else:
							data.append({
								'item_code': item,
								'item_group': item_map[item]["item_group"],
								'warehouse': wh,
								'batch_no': batch,
								'lot_no': lot_no,
								'voucher_type': qty_dict_without_group.voucher_type,
								'voucher_no': qty_dict_without_group.voucher_no,
								'concentration': concentration,
								'packaging_material': packaging_material,
								'packing_size': packing_size,
								'company':qty_dict.company,
								'packages': flt(qty_dict.bal_qty/packing_size,0) if packing_size else 0,
								'bal_qty': flt(qty_dict.bal_qty, float_precision),
								'amount': flt(qty_dict.bal_qty*valuation_rate, float_precision),
								'as_is_qty': flt(qty_dict.bal_qty, float_precision),
								'valuation_rate':valuation_rate,
								'uom': item_map[item]["stock_uom"],
								'party_type':qty_dict_without_group.party_type,
								'party':qty_dict_without_group.party,
							})
	current_fiscal_year = frappe.defaults.get_user_default("fiscal_year")
	from_date = frappe.db.get_value("Fiscal Year",current_fiscal_year,"year_start_date")
	to_date = filters.get('to_date')
	for row in data:
		item_code = row['item_code']
		batch_no = row['batch_no']
		company = row['company']
		row['stock_ledger'] = """<button style='margin-left:5px;border:none;color: #fff; background-color: #5e64ff; padding: 3px 5px;border-radius: 5px;'
			target="_blank" company='{company}' item_code='{item_code}' from_date='{from_date}' to_date='{to_date}' batch_no='{batch_no}'
			onClick=view_stock_leder_report(this.getAttribute('company'),this.getAttribute('item_code'),this.getAttribute('from_date'),this.getAttribute('to_date'),this.getAttribute('batch_no'))>View Stock Ledger</button>
			""".format(company=company, item_code=item_code,from_date=from_date,to_date=to_date,batch_no=batch_no)

	return columns, data

def get_columns(filters):
	"""return columns based on filters"""
	columns = [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 180
		},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 100
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120
		},
		{
			"label": _("Batch"),
			"fieldname": "batch_no",
			"fieldtype": "Link",
			"options": "Batch",
			"width": 120
		},
		{
			"label": _("Lot No"),
			"fieldname": "lot_no",
			"fieldtype": "Data",
			"width": 80
		},
		{
			"label": _("Receipt Document"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 140
		},
	]
	if filters.get('show_party'):
		columns +=[
			{"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "width": 80,"align":"center"},
			{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 140,"align":"left"},
		]
	columns +=[
		{
			"label": _("Concentration"),
			"fieldname": "concentration",
			"fieldtype": "Percent",
			"width": 80
		},
		{
			"label": _("Packages"),
			"fieldname": "packages",
			"fieldtype": "Int",
			"width": 50
		},		
		{
			"label": _("Size"),
			"fieldname": "packing_size",
			"fieldtype": "Data",
			"width": 50
		},
		{
			"label": _("Packaging Material"),
			"fieldname": "packaging_material",
			"fieldtype": "Link",
			"options": "Packaging Material",
			"width": 70
		},
		{
			"label": _("Qty"),
			"fieldname": "bal_qty",
			"fieldtype": "Float",
			"width": 90
		},
		{
			"label": _("Price"),
			"fieldname": "valuation_rate",
			"fieldtype": "Currency",
			"width": 80
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 80
		},
		# {
		# 	"label": _("As is Qty"),
		# 	"fieldname": "as_is_qty",
		# 	"fieldtype": "Float",
		# 	"width": 100
		# },
		
		{
			"label": _("UOM"),
			"fieldname": "uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 40
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 120
		},
				{
			"label": _("Voucher Type"),
			"fieldname": "voucher_type",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Stock Ledger"),
			"fieldname": "stock_ledger",
			"fieldtype": "button",
			"width": 120
		}
	]

	return columns

def get_conditions(filters):
	conditions = ""
	if filters.get("to_date"):
		conditions += " and sle.posting_date <= '%s'" % filters["to_date"]
	else:
		frappe.throw(_("'To Date' is required"))

	if filters.get("company"):
		conditions += " and sle.company = '%s'" % filters["company"]

	if filters.get("warehouse"):
		conditions += " and sle.warehouse = '%s'" % filters["warehouse"]

	if filters.get("item_code"):
		conditions += " and sle.item_code = '%s'" % filters["item_code"]

	return conditions

#get all details
def get_stock_ledger_entries(filters):
	# show_party_select = show_party_join = ''
	# if filters.get('show_party'):
	# 	show_party_join += " Left JOIN `tabStock Entry` as se on se.name = sle.voucher_no"
	# 	show_party_select += ", se.party_type, se.party"

	conditions = get_conditions(filters)
	return frappe.db.sql("""
		select sle.item_code, sle.batch_no, sle.warehouse, sle.posting_date,sle.company, sum(sle.actual_qty) as actual_qty
		from `tabStock Ledger Entry` as sle
		where sle.docstatus < 2 and ifnull(sle.batch_no, '') != '' %s
		group by sle.voucher_no, sle.batch_no, sle.item_code, sle.warehouse
		order by sle.item_code, sle.warehouse, sle.batch_no""" %
		conditions, as_dict=1)

def get_item_warehouse_batch_map(filters, float_precision):
	sle = get_stock_ledger_entries(filters)
	iwb_map = {}

	from_date = getdate(filters["to_date"])
	to_date = getdate(filters["to_date"])

	for d in sle:
		iwb_map.setdefault(d.company, {}).setdefault(d.item_code, {}).setdefault(d.warehouse, {})\
			.setdefault(d.batch_no, frappe._dict({
				"opening_qty": 0.0, "in_qty": 0.0, "out_qty": 0.0, "bal_qty": 0.0
			}))
		qty_dict = iwb_map[d.company][d.item_code][d.warehouse][d.batch_no]
		if d.posting_date < from_date:
			qty_dict.opening_qty = flt(qty_dict.opening_qty, float_precision) \
				+ flt(d.actual_qty, float_precision)
		elif d.posting_date >= from_date and d.posting_date <= to_date:
			if flt(d.actual_qty) > 0:
				qty_dict.in_qty = flt(qty_dict.in_qty, float_precision) + flt(d.actual_qty, float_precision)
			else:
				qty_dict.out_qty = flt(qty_dict.out_qty, float_precision) \
					+ abs(flt(d.actual_qty, float_precision))
		# qty_dict.party_type = d.party_type
		# qty_dict.party = d.party
		qty_dict.company = d.company
		qty_dict.bal_qty = flt(qty_dict.bal_qty, float_precision) + flt(d.actual_qty, float_precision)

	return iwb_map

def get_stock_ledger_entries_without_group(filters):
	show_party_select = show_party_join = ''
	if filters.get('show_party'):
		show_party_join += " Left JOIN `tabStock Entry` as se on se.name = sle.voucher_no"
		show_party_select += ", se.party_type, se.party"

	conditions = get_conditions(filters)
	return frappe.db.sql("""
		select sle.item_code, sle.batch_no, sle.warehouse, sle.posting_date,sle.company, sle.actual_qty, sle.voucher_type,sle.voucher_no %s
		from `tabStock Ledger Entry` as sle %s
		where sle.docstatus < 2 and ifnull(sle.batch_no, '') != '' and sle.actual_qty > 0 %s
		order by sle.item_code, sle.warehouse,sle.batch_no""" %
		(show_party_select, show_party_join,conditions), as_dict=1)

def get_item_warehouse_batch_map_without_group(filters, float_precision):
	sle = get_stock_ledger_entries_without_group(filters)
	iwb_map_without_group = {}

	for d in sle:
		iwb_map_without_group.setdefault(d.company, {}).setdefault(d.item_code, {}).setdefault(d.warehouse, {})\
			.setdefault(d.batch_no, frappe._dict({
				"voucher_type":'',"voucher_no":''
			}))
		qty_dict_without_group = iwb_map_without_group[d.company][d.item_code][d.warehouse][d.batch_no]
		qty_dict_without_group.voucher_type = d.voucher_type
		qty_dict_without_group.voucher_no = d.voucher_no
		qty_dict_without_group.party_type = d.party_type
		qty_dict_without_group.party = d.party

	return iwb_map_without_group


def get_item_details(filters):
	item_map = {}
	for d in frappe.db.sql("select name, item_name, description, stock_uom, item_group, maintain_as_is_stock from tabItem", as_dict=1):
		item_map.setdefault(d.name, d)

	return item_map

@frappe.whitelist()
def show_party_hidden():
	doc = frappe.get_doc({"doctype":"Stock Entry"})
	if hasattr(doc,'party'):
		return 1
	else:
		return 0