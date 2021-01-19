// Copyright (c) 2016, FinByz Tech Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Batch Wise Balance Chemical"] = {
	onload: function(report){
		frappe.call({
			method:"evergreen.evergreen.report.batch_wise_balance_chemical.batch_wise_balance_chemical.show_party_hidden",
			callback: function(r){
				if (r.message==0){
					frappe.query_report.get_filter('show_party').toggle(false)
				}
			}
		})
	},
	"filters": [
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"width": "80",
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
			"width": "80",
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": "80",
		},
		{
			"fieldname": "show_party",
			"label": __("Show party"),
			"fieldtype": "Check",
		}
		
	]
}
function view_stock_leder_report(company,item_code, from_date, to_date, batch_no) {
	window.open(window.location.href.split("#")[0] + "#query-report/Stock Ledger" + "/?" + "item_code=" + item_code  + "&" + "company=" + company+  "&" + "from_date=" + from_date + "&" + "to_date=" + to_date + "&" + "batch_no=" + batch_no,"_blank")	
}
