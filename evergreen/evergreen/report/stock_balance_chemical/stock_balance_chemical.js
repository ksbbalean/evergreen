// Copyright (c) 2016, FinByz Tech Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Stock Balance Chemical"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Company",
			"default": frappe.defaults.get_default("company")
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today()),
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item Group"
		},
		{
			"fieldname": "item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Item",
			"get_query": function () {
				return {
					query: "erpnext.controllers.queries.item_query",
				};
			}
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Warehouse",
			get_query: () => {
				var warehouse_type = frappe.query_report.get_filter_value('warehouse_type');
				if (warehouse_type) {
					return {
						filters: {
							'warehouse_type': warehouse_type
						}
					};
				}
			}
		},
		{
			"fieldname": "warehouse_type",
			"label": __("Warehouse Type"),
			"fieldtype": "Link",
			"width": "80",
			"options": "Warehouse Type"
		},
		// {
		// 	"fieldname": "include_uom",
		// 	"label": __("Include UOM"),
		// 	"fieldtype": "Link",
		// 	"options": "UOM"
		// },
		// {
		// 	"fieldname": "show_variant_attributes",
		// 	"label": __("Show Variant Attributes"),
		// 	"fieldtype": "Check"
		// },
		{
			"fieldname": 'show_stock_ageing_data',
			"label": __('Show Stock Ageing Data'),
			"fieldtype": 'Check'
		},
		{
			"fieldname": 'show_in_out_qty',
			"label": __('Show In/Out Qty'),
			"fieldtype": 'Check'
		},

	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "out_qty" && data && data.out_qty > 0) {
			value = "<span style='color:red'>" + value + "</span>";
		}
		else if (column.fieldname == "in_qty" && data && data.in_qty > 0) {
			value = "<span style='color:green'>" + value + "</span>";
		}

		return value;
	}
}
function view_batch_wise_report(item_code, company, to_date) {
	window.open(window.location.href.split("#")[0] + "#query-report/Batch Wise Balance Chemical" + "/?" + "item_code=" + item_code + "&" + "company="+company + "&" + "to_date=" + to_date,"_blank")	
}
function view_stock_leder_report(item_code,company, from_date, to_date) {
	window.open(window.location.href.split("#")[0] + "#query-report/Stock Ledger" + "/?" + "item_code=" + item_code + "&" + "company=" + company + "&" + "from_date=" + from_date + "&" + "to_date=" + to_date,"_blank")	
}
$(window).on("load resize scroll",function(){
    setTimeout(function(){
		
        var wh = $(window).height();
		var topPosition = wh - $('.page-form').height()
		// console.log('Nav: '+$('.navbar').height())
		// console.log('page head: '+$('.page-head').height())
		// console.log('page form: '+$('.page-form').height())
		// console.log('Dt Header: '+$('.dt-header').height())

		// console.log('window: '+wh)
        console.log('window: '+wh)
        console.log(wh)
        console.log(topPosition)
        final = topPosition - 200
		console.log(final)
		$('.dt-scrollable').height(final)
		//$('.dt-scrollable').css('height','500px');
	 },10);
});
$('.dt-scrollable').ready(function(){
	
	setTimeout(function(){
        var wh = $(window).height();
		var topPosition = wh - $('.page-form').height()
		// console.log('Nav: '+$('.navbar').height())
		// console.log('page head: '+$('.page-head').height())
		// console.log('page form: '+$('.page-form').height())
		// console.log('Dt Header: '+$('.dt-header').height())

        // console.log('window: '+wh)
		// console.log(topPosition)
		final = topPosition - 200
		console.log(final)
		console.log($('.dt-scrollable'))
		console.log($('.page-form').height())
		//$('.dt-scrollable').height(final)
		$('.dt-scrollable').attr('style', 'height: 100px !important');
		//$('.dt-scrollable').css('height','500');
    },10);
});