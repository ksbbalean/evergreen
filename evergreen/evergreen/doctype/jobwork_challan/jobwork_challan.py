# -*- coding: utf-8 -*-
# Copyright (c) 2019, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, get_url_to_form
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc


class JobworkChallan(Document):
	def validate(self):
		self.calculate_total()
		self.update_status()

	def calculate_total(self):
		self.total_qty = sum([row.qty for row in self.items])
		self.total_amount = sum([row.net_amount for row in self.items])

	def on_submit(self):
		se = frappe.new_doc("Stock Entry")
		se.posting_date = self.date
		se.purpose = "Material Transfer"
		se.naming_series = "STE-"
		se.company = self.company
		
		abbr = frappe.db.get_value("Company",self.company,'abbr')
		
		for row in self.items:
			se.append("items",{
				'item_code': row.item_code,
				's_warehouse': row.warehouse,
				't_warehouse': 'Jobwork - ' + abbr,
				'qty': row.qty,
				'batch_no': row.batch_no,
				'basic_rate': row.rate,
				'lot_no': row.lot_no,
				'packaging_material': row.packaging_material,
				'packing_size': row.packing_size,
				'batch_yield': row.batch_yield,
				'concentration': row.concentration
			})
		
		try:
			se.save()
			self.db_set('stock_entry', se.name)
			se.submit()
			frappe.db.commit()
			url = get_url_to_form("Stock Entry", se.name)
			frappe.msgprint("New Stock Entry - <a href='{url}'>{doc}</a> created for Material Transfer".format(url=url, doc=frappe.bold(se.name)))
		except:
			frappe.msgprint("Error creating Stock Entry", title="Error", indicator='red')
			frappe.db.rollback()
			self.reload()

	def on_cancel(self):
		self.cancel_received()
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry",self.stock_entry)
			self.db_set('stock_entry','')
			se.cancel()
			url = get_url_to_form("Stock Entry", se.name)
			frappe.db.commit()
			frappe.msgprint("Cancelled Stock Entry - <a href='{url}'>{doc}</a>".format(url=url, doc=frappe.bold(se.name)))
		
	def return_stock_entry(self, qty, received_date):
		se = frappe.new_doc("Stock Entry")
		se.posting_date = received_date
		se.purpose = "Repack"
		se.naming_series = "STE-"
		se.company = self.company
		
		abbr = frappe.db.get_value("Company",self.company,'abbr')
	
		for row in self.items:
			se.append("items",{
				'item_code': row.item_code,
				's_warehouse': 'Jobwork - ' + abbr,
				'qty': row.qty,
				'batch_no': row.batch_no,
				'basic_rate': row.rate,
				'lot_no': row.lot_no,
				'packaging_material': row.packaging_material,
				'packing_size': row.packing_size,
				'batch_yield': row.batch_yield,
				'concentration': row.concentration
			})

		se.append("items",{
			'item_code': self.finished_product,
			't_warehouse': self.finished_product_warehouse,
			'qty': qty,
		})
		
		se.save()
		self.db_set('received_stock_entry' , se.name)
		self.db_set('status' , "Received")
		se.submit()
		frappe.db.commit()
		
	def cancel_received(self):
		if self.received_stock_entry:
			ser = frappe.get_doc("Stock Entry",self.received_stock_entry)
			self.db_set('received_stock_entry','')
			ser.cancel()

	def update_status(self):
		status = self.status

		if self.docstatus==0:
			status = 'Draft'
		elif self.docstatus==1:
			total_received_qty = sum([max(flt(row.received_qty),0) for row in self.items])

			if not total_received_qty:
				status = "Sent"
			elif self.total_qty == total_received_qty:
				status = "Received"
			else: 
				status = "Partially Received"
		else:
			status = "Cancelled"

		self.db_set('status', status)


@frappe.whitelist()
def make_jobwork_finish(source_name, target_doc=None):

	def postprocess(source, target):
		target.calculate_total()

	def update_item(source, target, source_parent):
		target.received_qty = flt(source.qty) - flt(source.received_qty)
		target.net_amount = target.received_qty * source.rate
	
	doclist = get_mapped_doc("Jobwork Challan", source_name, {
			"Jobwork Challan": {
				"doctype": "Jobwork Finish",
				"field_no_map": [
					"total_qty",
					"total_amount",
					"received_stock_entry"
				],
			},
			"Job Work Item": {
				"doctype": "Jobwork Finish Item",
				"field_map": {
					"name": "job_work_item",
					"parent": "jobwork_challan",
				},
				"field_no_map": {
					"net_amount"
				},
				"postprocess": update_item,
				"condition": lambda doc: doc.received_qty < doc.qty
			}
		}, target_doc, postprocess)

	return doclist