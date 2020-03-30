// Copyright (c) 2018, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt


cur_frm.fields_dict.product_name.get_query = function(doc) {
	return {
		filters: {
			"item_group": 'FINISHED DYES'
		}
	}
};
cur_frm.fields_dict.sample_no.get_query = function(doc) {
	return {
		filters: {
			"product_name": doc.product_name,
			"party": doc.customer_name 
		}
	}
};
cur_frm.fields_dict.default_source_warehouse.get_query = function(doc) {
	return {
		filters: {
			"is_group": 0
		}
	}
};
this.frm.cscript.onload = function(frm) {
	this.frm.set_query("batch_no", "items", function(doc, cdt, cdn) {
		let d = locals[cdt][cdn];
		if(!d.item_name){
			frappe.msgprint(__("Please select Item"));
		}
		else if(!d.source_warehouse){
			frappe.msgprint(__("Please select source warehouse"));
		}
		else{
			return {
				query: "evergreen.batch_valuation.get_batch",
				filters: {
					'item_code': d.item_name,
					'warehouse': d.source_warehouse
				}
			}
		}
	});
}

frappe.ui.form.on("Ball Mill Data Sheet", {
	refresh: function(frm){
		if(frm.doc.docstatus == 1){
			frm.add_custom_button(__("Outward Sample"), function() {
				frappe.model.open_mapped_doc({
					method : "evergreen.evergreen.doctype.ball_mill_data_sheet.ball_mill_data_sheet.make_outward_sample",
					frm : cur_frm
				})
			}, __("Make"));
		}
	},
	sales_order:function(frm){
		if(!frm.doc.sales_order || frm.doc.sales_order == undefined ){
			frm.set_value('sample_no','')
			frm.set_value('lot_no','')
			return false;
		}
		else {
			frappe.call({
				method : "evergreen.evergreen.doctype.ball_mill_data_sheet.ball_mill_data_sheet.get_sample_no",
				args:{
					parent:frm.doc.sales_order,	
					item_code:frm.doc.product_name,
				},
				callback: function(r) {
					if(!r.exc){
						frm.set_value('sample_no',r.message)
					}
				}
			});
		}
	},
	product_name: function(frm) {
		frm.set_value('sales_order','')
		frm.set_value('sample_no','')
       
	},
	sample_no:function(frm){
		get_qty(frm);
		
	},
	target_qty:function(frm){
		get_qty(frm);
	},
});
function get_qty(frm) {
	if(flt(frm.doc.target_qty) != 0 && frm.doc.sample_no){
		frappe.run_serially([
			() => { frm.set_value('items',[]) },
			() => {
				frappe.model.with_doc("Outward Sample", frm.doc.sample_no, function() {
					frappe.run_serially([
						() => {
							let os_doc = frappe.model.get_doc("Outward Sample", frm.doc.sample_no)
							$.each(os_doc.details, function(index, row){
								let d = frm.add_child("items");
								d.item_name = row.item_name;
								d.source_warehouse = frm.doc.default_source_warehouse;
								d.quantity = flt(flt(frm.doc.target_qty * row.quantity) / os_doc.total_qty);
								d.required_quantity = flt(flt(frm.doc.target_qty * row.quantity) / os_doc.total_qty);
							})
						},
						() => {
							frm.refresh_fields("items");
						},
					])
				});
			},
		]);
	
	}
}

frappe.ui.form.on('Ball Mill Data Sheet Item', {
	items_add: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if(!row.source_warehouse && row.source_warehouse == undefined){
		 row.source_warehouse = cur_frm.doc.default_source_warehouse;
		 frm.refresh_field("items");
		}
	},
	concentration: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.required_quantity){
			frappe.model.set_value(cdt,cdn,"quantity",row.required_quantity*row.concentration)
			frappe.model.set_value(cdt,cdn,"required_quantity",row.required_quantity*row.concentration)
		}
	},
});
