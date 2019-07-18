# -*- coding: utf-8 -*-
# Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import db,_
from frappe.model.document import Document

class PurchasePrice(Document):
	def on_submit(self):
		data = frappe.get_list("Item Price",fields = 'item_code')
		if db.exists("Item Price" ,{ "item_code":self.product_name ,"price_list":self.price_list}):
			item_price = frappe.get_doc("Item Price",{"item_code":self.product_name, "price_list":self.price_list})
			item_price.price_list_rate = self.price
			item_price.price_list = self.price_list
			item_price.save()
		else:
			item_price = frappe.new_doc("Item Price")
			item_price.price_list = self.price_list
			item_price.item_code = self.product_name
			item_price.price_list_rate = self.price
			item_price.save()
		frappe.db.commit()
		frappe.msgprint(_("Item Price Updated"))

	def on_update_after_submit(self):
		self.on_submit()
