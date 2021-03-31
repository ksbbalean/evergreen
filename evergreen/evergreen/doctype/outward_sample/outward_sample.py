# -*- coding: utf-8 -*-
# Copyright (c) 2018, FinByz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, db
from frappe.utils import flt
from frappe.model.document import Document
from evergreen.api import get_spare_price,get_party_details
from frappe.model.mapper import get_mapped_doc
from frappe.desk.reportview import get_match_cond, get_filters_cond


class OutwardSample(Document):
	def before_save(self):
		party_detail = get_party_details(party = self.party,party_type = self.link_to)
		self.party_name = party_detail.party_name
		self.cal_yield_rate()
		self.get_master_sample()
		self.get_latest_ball_mill()
		self.get_latest_sample()
	
	def on_cancel(self):
		self.db_set('against','')
		
	# def get_ball_mill(self):
		# if not self.ball_mill_ref:
			# frappe.throw(_("Please select Ball Mill Data Sheet!"))

		# bm = frappe.get_doc("Ball Mill Data Sheet", self.ball_mill_ref)
		# self.product_name = bm.product_name
		# self.link_to = "Customer"
		# self.party = bm.customer_name
		# self.batch_yield = bm.total_yield

		# customer_name, destination = db.get_value("Customer", bm.customer_name, ['customer_name', 'territory'])
		# self.party_name = customer_name
		# self.destination_1 = self.destination = destination

		# self.set("details", [])

		# total_amount = 0.0
		# for row in bm.items:
			# price = get_spare_price(row.item_name, "Standard Buying").price_list_rate

			# if row.batch_yield:
				# bomyield = frappe.db.get_value("BOM",{'item': row.item_name},"batch_yield")
				# if bomyield != 0:
					# rate = (price * flt(bomyield)) / row.batch_yield
				# else:
					# rate = (price * 2.2) / row.batch_yield
			# else:
				# rate = price

			# amount = rate * row.quantity
			# total_amount += amount

			# self.append('details',{
					# 'item_name': row.item_name,
					# 'batch_yield': row.batch_yield,
					# 'quantity': row.quantity,
					# 'rate': rate,
					# 'price_list_rate': price,
					# 'amount': amount,

				# })

		# self.total_amount = total_amount
		# self.total_qty = bm.total_qty
		# self.per_unit_price = total_amount / bm.total_qty
		
	def cal_yield_rate(self):
		for row in self.details:
			if row.concentration:
				bom_concentration = frappe.db.get_value("BOM",{'item':row.item_name,'is_default':1},'concentration') or 100.0
				batch_yield = flt(frappe.db.get_value("BOM",{'item':row.item_name,'is_default':1},'batch_yield')) or 1.0
				if batch_yield:
					row.batch_yield = flt(batch_yield)* 100 / flt(row.concentration)
				
				if bom_concentration:
					rate = flt((row.price_list_rate * flt(row.concentration)) / bom_concentration)
				elif row.batch_yield and batch_yield:
					rate = flt((row.price_list_rate * batch_yield) / row.batch_yield)
				else:
					rate = flt(row.price_list_rate)
				row.rate = rate
	
	def get_master_sample(self):
		master_sample = db.sql("select name from `tabOutward Sample` \
				where docstatus = 1 and product_name = %s and party = %s and is_master_sample = 1", (self.product_name, self.party))

		if master_sample:
			self.master_sample = master_sample[0][0]
			
	def get_latest_ball_mill(self):
		ball_mill = db.sql("select name, date from `tabBall Mill Data Sheet` \
				where docstatus = 1 and product_name = %s and customer_name = %s ORDER BY date DESC", (self.product_name, self.party))
		if ball_mill:
			self.last_purchase_reference = ball_mill[0][0]
			
	def get_latest_sample(self):
		last_sample = db.sql("select name,date from `tabOutward Sample` \
				where docstatus = 1 and product_name = %s and party = %s ORDER BY date DESC", (self.product_name, self.party))
		if last_sample:
			self.last_sample = last_sample[0][0]
			
@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	def postprocess(source, target):
		target.append('items', {
			'item_code': source.product_name,
			'item_name': source.product_name,
			'base_cost' : source.per_unit_price
			})

	doclist = get_mapped_doc("Outward Sample" , source_name,{
		"Outward Sample":{
			"doctype" : "Quotation",
			"field_map":{
				"link_to" : "quotation_to",
				"party" : "customer",
				"date" : "transaction_date" ,
			},
		}
	},target_doc, postprocess)

	return doclist

@frappe.whitelist()
def get_outward_sample(doctype, txt, searchfield, start, page_len, filters, as_dict):
	return frappe.db.sql("""
		SELECT 
			`tabOutward Sample`.name, `tabOutward Sample`.date as transaction_date
		FROM
			`tabOutward Sample`
		WHERE
			`tabOutward Sample`.docstatus = 1
			%(fcond)s
			%(mcond)s
		""" % {
			"fcond": get_filters_cond(doctype, filters, []),
			"mcond": get_match_cond(doctype),
			"txt": "%(txt)s"
		}, {"txt": ("%%%s%%" % txt)}, as_dict=as_dict)