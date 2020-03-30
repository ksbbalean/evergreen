# -*- coding: utf-8 -*-
# Copyright (c) 2018, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
from frappe.model.document import Document
from frappe.utils import nowtime, flt
from erpnext.stock.utils import get_incoming_rate
from erpnext.stock.stock_ledger import get_valuation_rate
from frappe.model.mapper import get_mapped_doc

class BallMillDataSheet(Document):

	def validate(self):
		self.set_incoming_rate()
		self.cal_total()
		if self._action == 'submit':
			self.validate_qty()
		
	def set_incoming_rate(self):
		for d in self.items:
			if d.source_warehouse:
				args = self.get_args_for_incoming_rate(d)
				d.basic_rate = get_incoming_rate(args)
			elif not d.source_warehouse:
				d.basic_rate = 0.0
			elif self.warehouse and not d.basic_rate:
				d.basic_rate = get_valuation_rate(d.item_code, self.warehouse,
					self.doctype, d.name, 1,
					currency=erpnext.get_company_currency(self.company))

			d.basic_amount = d.basic_rate * d.quantity
	
	
	def get_args_for_incoming_rate(self, item):
		warehouse = item.source_warehouse or self.warehouse
		return frappe._dict({
			"item_code": item.item_name,
			"warehouse": warehouse,
			"posting_date": self.date,
			"posting_time": self.time,
			"qty": warehouse and -1*flt(item.quantity) or flt(item.quantity),
			"voucher_type": self.doctype,
			"voucher_no": item.name,
			"company": self.company,
			"allow_zero_valuation": 1,
			"batch_no":item.batch_no
		})
	
	def on_submit(self):
		se = frappe.new_doc("Stock Entry");
		se.purpose = "Repack"
		se.set_posting_time = 1
		se.company = "Evergreen Industries"
		se.posting_date = self.date
		se.posting_time = self.time
		se.from_ball_mill = 1
		for row in self.items:
			se.append('items',{
				'item_code': row.item_name,
				's_warehouse': row.source_warehouse,
				'batch_no': row.batch_no,
				'basic_rate': row.basic_rate,
				'basic_amount': row.basic_amount,
				'qty': row.quantity,
			})

		for d in self.packaging:	
			se.append('items',{
				'item_code': self.product_name,
				't_warehouse': self.warehouse,
				'qty': d.qty,
				'packaging_material': d.packaging_material,
				'packing_size': d.packing_size,
				'no_of_packages': d.no_of_packages,
				'lot_no': d.lot_no,
				'concentration': self.concentration,
				'basic_rate': self.per_unit_amount,
				'valuation_rate': self.per_unit_amount,
				#'basic_amount': flt(d.qty * self.per_unit_amount),
			})
		
		try:
			se.save()
			se.submit()
		except Exception as e:
			frappe.throw(str(e))
		else:
			self.db_set('stock_entry',se.name)

		for row in self.packaging:
			batch = frappe.db.sql("""
				SELECT sed.batch_no from `tabStock Entry` se LEFT JOIN `tabStock Entry Detail` sed on (se.name = sed.parent)
				WHERE 
					se.name = '{name}'
					and (sed.t_warehouse != '' or sed.t_warehouse IS NOT NULL) 
					and sed.qty = {qty}
					and sed.packaging_material = '{packaging_material}'
					and sed.packing_size = '{packing_size}'
					and sed.no_of_packages = {no_of_packages}""".format(
						name=se.name,
						qty=row.qty,
						packaging_material=row.packaging_material,
						packing_size=row.packing_size,
						no_of_packages=row.no_of_packages,
					))[0][0] or ''

			if batch:
				row.db_set('batch_no', batch)
				frappe.db.set_value("Batch",batch,'customer',self.customer_name)
				if self.lot_no:
					frappe.db.set_value("Batch",batch,'sample_ref_no',self.lot_no)

		frappe.db.commit()
		
	def on_cancel(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry",self.stock_entry)
			se.cancel()
			self.db_set('stock_entry','')
			frappe.db.commit()

			for row in self.packaging:
				row.db_set('batch_no', '')
		
	def cal_total(self):
		self.amount = sum([flt(row.basic_amount) for row in self.items])
		self.per_unit_amount = self.amount/ self.actual_qty
	
	def validate_qty(self):
		total_qty = sum([flt(row.qty) for row in self.packaging])
		if self.actual_qty != total_qty:
			frappe.throw("Sum of Qty should be match with actual qty")

@frappe.whitelist()
def make_outward_sample(source_name, target_doc=None):
	def postprocess(source, doc):
		from evergreen.api import get_spare_price

		doc.link_to = "Customer"
		customer_name, destination = frappe.db.get_value("Customer", doc.party, ['customer_name', 'territory'])
		doc.party_name = customer_name
		doc.destination_1 = doc.destination = destination

		total_amount = 0.0
		for d in doc.details:
			price = get_spare_price(d.item_name, "Standard Buying").price_list_rate

			if d.batch_yield:
				bomyield = frappe.db.get_value("BOM",{'item': d.item_name},"batch_yield")
				if bomyield != 0:
					d.rate = (price * flt(bomyield)) / d.batch_yield
				else:
					d.rate = (price * 2.2) / d.batch_yield
			else:
				d.rate = price
			
			d.price_list_rate = price
			d.amount = flt(d.rate) * d.quantity
			total_amount += d.amount

		doc.total_amount = total_amount
		doc.total_qty = source.actual_qty
		doc.per_unit_price = flt(total_amount) / flt(doc.total_qty)

	doc = get_mapped_doc("Ball Mill Data Sheet", source_name, {
		"Ball Mill Data Sheet": {
			"doctype": "Outward Sample",
			"validation": {
				"docstatus": ["=", 1]
			},
			"field_map": {
				"name": 'ball_mill_ref',
				"customer_name": "party",
				"total_yield": "batch_yield"
			},
			"field_no_map": [
				"naming_series",
				"remarks"
			]
		},
		"Ball Mill Data Sheet Item": {
			"doctype": "Outward Sample Detail",
		}
	}, target_doc, postprocess)

	return doc
	
def get_sales_order(doctype, txt, searchfield, start, page_len, filters):
	meta = frappe.get_meta("Sales Order")
	searchfield = meta.get_search_fields()

	sales_order_list = frappe.db.sql("""
			SELECT so.name from `tabSales Order` as so 
			LEFT JOIN `tabSales Order Item` as soi 
			ON so.name = soi.parent
			WHERE so.docstatus = '1' and so.customer  = '{0}' and soi.item_code = '{1}' """ 
			.format(filters.get("customer_name"),filters.get("product_name")))
	
	return sales_order_list
	
@frappe.whitelist()
def get_sample_no(parent,item_code):
	value = frappe.db.get_value("Sales Order Item", {'parent': parent,'item_code': item_code}, 'outward_sample')
	return value
	