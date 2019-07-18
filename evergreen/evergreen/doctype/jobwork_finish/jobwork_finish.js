// Copyright (c) 2019, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Jobwork Finish', {
	setup: function(frm){
		frm.add_fetch('bom_no', 'based_on', 'based_on');
	},

	refresh: function(frm) {
		if (frm.doc.docstatus===0) {
			frm.add_custom_button(__('Jobwork Challan'),
				function() {
					erpnext.utils.map_current_doc({
						method: "evergreen.evergreen.doctype.jobwork_challan.jobwork_challan.make_jobwork_finish",
						source_doctype: "Jobwork Challan",
						target: cur_frm,
						date_field: 'date',
						setters: {
							finished_product: cur_frm.doc.finished_product || undefined,
						},
						get_query_filters: {
							docstatus: 1,
							status: ['in', ["Sent", "Partially Received"]]
						}
					})
				}, __("Get items from"));
		}
	},

	before_save: function(frm){
		if(frm.doc.additional_costs != undefined){
			if(frm.doc.additional_costs.length == 0 && frm.doc.volume_cost){
				var m = frm.add_child("additional_costs");
				m.description = "Spray Drying Cost";
				m.amount = frm.doc.volume_cost;
			} else {
				frm.doc.additional_costs.forEach(function(d){
					if(d.description == "Spray Drying Cost"){
						d.amount = frm.doc.volume_cost;
						return;
					}
				})
			}
		}
	},

	volume: function(frm){
		frm.set_value('volume_cost', flt(frm.doc.volume * frm.doc.volume_rate));
	},

	volume_rate: function(frm){
		frm.set_value('volume_cost', flt(frm.doc.volume * frm.doc.volume_rate));
	},
});

frappe.ui.form.on("Jobwork Finish Item", {
	received_qty: function(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'net_amount', flt(d.received_qty * d.rate))
	}
});