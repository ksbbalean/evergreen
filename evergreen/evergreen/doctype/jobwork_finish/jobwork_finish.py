# -*- coding: utf-8 -*-
# Copyright (c) 2019, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate, get_url_to_form
from frappe.model.document import Document

class JobworkFinish(Document):
	def validate(self):
		self.validate_fields()
		self.calculate_total()
		self.calculate_batch_yield()

		if self._action == 'submit':
			self.validate_qty()

	def before_save(self):
		self.update_additional_cost()

	def validate_fields(self):
		for row in self.items:
			if not row.jobwork_challan:
				frappe.throw(_("Jobwork Challan Reference is required at row {}!".format(row.idx)))

		if not flt(self.finished_product_qty):
			frappe.throw(_("Please provide Finished Product Quantity!"))

		if getdate(self.received_date) < getdate(self.date):
			frappe.throw(_("Received Date cannot be before Jobwork Date."))

	def calculate_total(self):
		self.total_qty = sum([row.received_qty for row in self.get('items')])
		self.total_amount = sum([row.net_amount for row in self.get('items')])

	def calculate_batch_yield(self):
		items_list = [row.item_code for row in self.items]

		based_on = ""
		if not self.based_on and "Vinyl Sulphone (V.S)" in items_list:
			based_on = "Vinyl Sulphone (V.S)"
		elif self.based_on in items_list:
			based_on = self.based_on

		if based_on:
			based_on_qty = sum([flt(row.received_qty) for row in self.items if row.item_code == based_on])
			self.batch_yield = flt((self.finished_product_qty / flt(based_on_qty) * (self.concentration / 100.0)), 3)

	def validate_qty(self):
		for row in self.items:
			item_recv_qty, item_total_qty = frappe.db.get_value("Job Work Item", row.job_work_item, ['received_qty', 'qty'])

			total_received_qty = flt(item_recv_qty + row.received_qty, 2)
			if total_received_qty > item_total_qty:
				frappe.throw(_("Row #{0}: Total finished qty {1} exceeds Jobwork Challan qty {2} for item {3}".format(row.idx, row.received_qty, item_total_qty, frappe.bold(row.item_code))))

	def on_submit(self):
		self.stock_entry_received()
		self.update_item_qty()
		self.update_jobwork_status()

	def on_cancel(self):
		self.cancel_received()
		self.update_item_qty()
		self.update_jobwork_status()

	def update_jobwork_status(self):
		for row in self.items:
			frappe.get_doc("Jobwork Challan", row.jobwork_challan).update_status()
		
	def update_item_qty(self):
		for row in self.items:
			item_doc = frappe.get_doc("Job Work Item", row.job_work_item)
			if self._action == 'submit':
				received_qty = min(flt(item_doc.received_qty + row.received_qty),item_doc.qty)
			else:
				received_qty = max(flt(item_doc.received_qty - row.received_qty),0)

			item_doc.db_set('received_qty', flt(received_qty))

	def stock_entry_received(self):
		se = frappe.new_doc("Stock Entry")
		se.posting_date = self.received_date
		se.purpose = "Repack"
		se.naming_series = "STE-"
		se.company = self.company
		se.volume = self.volume
		se.volume_rate = self.volume_rate
		se.volume_cost = self.volume_cost
		
		abbr = frappe.db.get_value("Company",self.company,'abbr')

		if self.get('bom_no'):
			se.from_bom = 1
			se.bom_no = self.bom_no
			se.fg_completed_qty = flt(self.finished_product_qty)
			se.based_on = self.based_on
	
		for row in self.items:
			se.append("items",{
				'item_code': row.item_code,
				's_warehouse': 'Jobwork - ' + abbr,
				'qty': row.received_qty,
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
			'qty': self.finished_product_qty,
			'packaging_material': self.packaging_material,
			'packing_size': self.packing_size,
			'lot_no': self.lot_no,
			'concentration': self.concentration,
			'batch_yield': self.batch_yield,
		})

		for row in self.additional_costs:
			se.append('additional_costs', {
				'description': row.description,
				'amount': row.amount,
			})

		try:
			se.save()
			se.submit()
			self.db_set('received_stock_entry' , se.name)
			self.db_set('valuation_rate' , se.items[-1].valuation_rate)
			url = get_url_to_form("Stock Entry", se.name)
			frappe.msgprint("New Stock Entry - <a href='{url}'>{doc}</a> created of Repack for Finished Product".format(url=url, doc=frappe.bold(se.name)))
		except:
			frappe.db.rollback()
			frappe.throw(_("Error creating Stock Entry"), title="Error")

	def cancel_received(self):
		if self.received_stock_entry:
			se = frappe.get_doc("Stock Entry",self.received_stock_entry)
			se.cancel()
			frappe.db.commit()
			self.db_set('received_stock_entry','')
			url = get_url_to_form("Stock Entry", se.name)
			frappe.msgprint("Cancelled Stock Entry - <a href='{url}'>{doc}</a>".format(url=url, doc=frappe.bold(se.name)))

	def update_additional_cost(self):
		if self.is_new() and not self.amended_from:
			self.append("additional_costs",{
				'description': "Spray drying cost",
				'amount': self.volume_cost
			})
		else:
			for row in self.additional_costs:
				if row.description == "Spray drying cost":
					row.amount = self.volume_cost
				break