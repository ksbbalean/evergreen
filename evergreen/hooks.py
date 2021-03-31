# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "evergreen"
app_title = "Evergreen"
app_publisher = "Finbyz Tech Pvt Ltd"
app_description = "Custom App For Evergreen"
app_icon = "octicon octicon-beaker"
app_color = "orange"
app_email = "info@finbyz.com"
app_license = "GPL 3.0"


#payment term override
from evergreen.api import get_due_date
from erpnext.controllers import accounts_controller
accounts_controller.get_due_date = get_due_date


# overide reason bcz raw material changes on change event of fg_completed_qty
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from evergreen.api import get_items
StockEntry.get_items = get_items

from erpnext.controllers.stock_controller import StockController
from evergreen.api import delete_auto_created_batches
StockController.delete_auto_created_batches = delete_auto_created_batches

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/evergreen/css/evergreen.css"
# app_include_js = "/assets/evergreen/js/evergreen.js"

# app_include_js = [
	# "assets/js/summernote.min.js",
	# "assets/js/comment_desk.min.js",
	# "assets/js/editor.min.js",
	# "assets/js/timeline.min.js"
# ]

# app_include_css = [
	# "/assets/css/evergreen.min.css",
	# "assets/css/summernote.min.css"
# ]
doctype_js = {
	"Production Plan": "public/js/doctype_js/production_plan.js",
	"Sales Invoice": "public/js/doctype_js/sales_invoice.js",
	"Purchase Invoice": "public/js/doctype_js/purchase_invoice.js",
	"Purchase Order": "public/js/doctype_js/purchase_order.js",
	"Delivery Note" : "public/js/doctype_js/delivery_note.js",
	"Purchase Receipt" : "public/js/doctype_js/purchase_receipt.js",
	"Sales Order": "public/js/doctype_js/sales_order.js",
	"Stock Entry": "public/js/doctype_js/stock_entry.js",
}
	

# include js, css files in header of web template
# web_include_css = "/assets/evergreen/css/evergreen.css"
# web_include_js = "/assets/evergreen/js/evergreen.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

override_whitelisted_methods = {
 	"frappe.core.page.permission_manager.permission_manager.get_roles_and_doctypes": "evergreen.permission.get_roles_and_doctypes",
 	"frappe.core.page.permission_manager.permission_manager.get_permissions": "evergreen.permission.get_permissions",
	"frappe.core.page.permission_manager.permission_manager.add": "evergreen.permission.add",
	"frappe.core.page.permission_manager.permission_manager.update": "evergreen.permission.update",
	"frappe.core.page.permission_manager.permission_manager.remove": "evergreen.permission.remove",
	"frappe.core.page.permission_manager.permission_manager.reset": "evergreen.permission.reset",
	"frappe.core.page.permission_manager.permission_manager.get_users_with_role": "evergreen.permission.get_users_with_role",
	"frappe.core.page.permission_manager.permission_manager.get_standard_permissions": "evergreen.permission.get_standard_permissions",
	"erpnext.manufacturing.doctype.bom_update_tool.bom_update_tool.enqueue_update_cost": "evergreen.api.enqueue_update_cost",
	"frappe.utils.print_format.download_pdf": "evergreen.print_format.download_pdf",
}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "evergreen.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "evergreen.install.before_install"
# after_install = "evergreen.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "evergreen.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"evergreen.tasks.all"
# 	],
# 	"daily": [
# 		"evergreen.tasks.daily"
# 	],
# 	"hourly": [
# 		"evergreen.tasks.hourly"
# 	],
# 	"weekly": [
# 		"evergreen.tasks.weekly"
# 	]
# 	"monthly": [
# 		"evergreen.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "evergreen.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "evergreen.event.get_events"
# }


doc_events = {
	"Stock Entry": {
		"validate": [
			"evergreen.batch_valuation.stock_entry_validate",
			"evergreen.api.stock_entry_validate"
		],
		"before_save": "evergreen.api.stock_entry_before_save",
		"before_submit": "evergreen.api.override_po_functions",
		"on_submit": [
			"evergreen.batch_valuation.stock_entry_on_submit",
			"evergreen.api.stock_entry_on_submit",
		],
		"before_cancel": "evergreen.api.override_po_functions",
		"on_cancel": [
			"evergreen.api.stock_entry_on_cancel",
			"evergreen.batch_valuation.stock_entry_on_cancel",
		],
	},
	"BOM": {
		"before_save": "evergreen.api.bom_before_save",
	},
	"Item Price": {
		"before_save": "evergreen.api.IP_before_save",
	},
	"Customer":{
		"before_rename": "evergreen.api.customer_override_after_rename",
		"autoname": "evergreen.api.customer_auto_name",
	},
	"Supplier":{
		"before_rename": "evergreen.api.supplier_override_after_rename",
		"autoname": "evergreen.api.supplier_auto_name",
	},
	"Sales Invoice": {
		"onload": "evergreen.api.si_onload",
		"on_submit": "evergreen.api.si_on_submit",
		"on_cancel": "evergreen.api.si_on_cancel",
		"validate": "evergreen.api.si_validate",
		"before_update_after_submit": "evergreen.api.before_update_after_submit",
	},
	"Purchase Invoice": {
		"onload": "evergreen.api.pi_onload",
		"validate": [
			"evergreen.batch_valuation.pi_validate",
			"evergreen.api.pi_validate"
		],
		"before_submit": "evergreen.api.pi_before_submit",
		"on_submit": "evergreen.api.pi_on_submit",
		"on_cancel": [
			"evergreen.api.pi_on_cancel", 
			"evergreen.batch_valuation.pi_on_cancel",
		],
		"on_update_after_submit": "evergreen.api.pi_on_update",
	},
	"Batch": {
		'before_naming': "evergreen.batch_valuation.override_batch_autoname",
	},
	"Payment Entry": {
		"before_save": "evergreen.api.pe_before_save",
		"on_submit" : "evergreen.api.pe_on_submit",
	},
	"Purchase Receipt": {
		"validate": "evergreen.batch_valuation.pr_validate",
		"on_cancel": "evergreen.batch_valuation.pr_on_cancel",
		"on_submit": "evergreen.api.pr_on_submit",
		"before_cancel": "evergreen.api.pr_before_cancel"
	},
	"Landed Cost Voucher": {
		"validate": "evergreen.batch_valuation.lcv_validate",
		"on_submit": "evergreen.batch_valuation.lcv_on_submit",
		"on_cancel": "evergreen.batch_valuation.lcv_on_cancel",
	},
	"Item": {
		"validate": "evergreen.api.item_validate",
	},
	"Delivery Note": {
		"validate":"evergreen.api.dn_validate",
		"on_submit": "evergreen.api.dn_on_submit",
		"before_cancel": "evergreen.api.dn_before_cancel",
	},
	"Stock Ledger Entry": {
		"before_submit": "evergreen.api.sl_before_submit"
	},
	("Sales Invoice", "Purchase Invoice", "Payment Request", "Payment Entry", "Journal Entry", "Material Request", "Purchase Order", "Work Order", "Production Plan", "Stock Entry", "Quotation", "Sales Order", "Delivery Note", "Purchase Receipt", "Packing Slip"): {
		"before_naming": "evergreen.api.docs_before_naming",
	},
	"Fiscal Year": {
		'before_save': 'evergreen.api.fiscal_before_save'
	},
}

scheduler_events = {
	"daily":[
		"evergreen.api.upadte_item_price_daily"
	]
}