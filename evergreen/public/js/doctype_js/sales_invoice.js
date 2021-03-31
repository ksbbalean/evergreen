cur_frm.add_fetch('advance_authorisation_license', 'approved_qty', 'license_qty');
cur_frm.add_fetch('advance_authorisation_license', 'remaining_export_qty', 'license_remaining_qty');
cur_frm.add_fetch('advance_authorisation_license', 'approved_amount', 'license_amount');
cur_frm.add_fetch('advance_authorisation_license', 'remaining_export_amount', 'license_remaining_amount');



this.frm.add_fetch('batch_no', 'packaging_material', 'packaging_material');
this.frm.add_fetch('batch_no', 'packing_size', 'packing_size');
this.frm.add_fetch('batch_no', 'sample_ref_no', 'lot_no');
this.frm.add_fetch('batch_no', 'batch_yield', 'batch_yield');
this.frm.add_fetch('batch_no', 'concentration', 'concentration');

cur_frm.fields_dict.supplier_transporter.get_query = function (doc) {
    return {
        filters: {
            "supplier_type": "Transporter"
        }
    }
};

// Customer Address Filter
cur_frm.set_query("customer_address", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: {
            link_doctype: "Customer",
            link_name: cur_frm.doc.customer
        }
    };
});

// Shipping Address Filter
cur_frm.set_query("shipping_address_name", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
    };
});

// Customer Contact Filter
cur_frm.set_query("contact_person", function () {
    return {
        query: "frappe.contacts.doctype.contact.contact.contact_query",
        filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
    };
});


// Address Filter
cur_frm.set_query("notify_party", function () {
    return {
        query: "frappe.contacts.doctype.address.address.address_query",
        filters: { link_doctype: "Customer", link_name: cur_frm.doc.customer }
    };
});

cur_frm.fields_dict.custom_address.get_query = function (doc) {
    return {
        filters: [
            ["address_type", "in", ["Consignee-Custom", "Custom"]],
            ["link_name", "=", cur_frm.doc.customer]
        ]
    }
};

cur_frm.fields_dict.items.grid.get_field("advance_authorisation_license").get_query = function (doc, cdt, cdn) {
    let d = locals[cdt][cdn];
    return {
        filters: {
            "export_item": d.item_code,
        }
    }
};
cur_frm.fields_dict.set_warehouse.get_query = function (doc) {
	return {
		filters: {
			"company": doc.company,
            "is_group":0,
		}
	}
};
cur_frm.fields_dict.items.grid.get_field("warehouse").get_query = function (doc) {
	return {
		filters: {
			"company": doc.company,
            "is_group":0,
		}
	}
};
cur_frm.fields_dict.taxes_and_charges.get_query = function (doc) {
	return {
		filters: {
			"company": doc.company,
		}
	}
};

frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        if (cint(cur_frm.doc.docstatus == 0) && cur_frm.page.current_view_name !== "pos" && !cur_frm.doc.is_return) {
            cur_frm.add_custom_button(__('Shipping Document'), function () {
                erpnext.utils.map_current_doc({
                    method: "evergreen.evergreen.doctype.shipping_document.shipping_document.make_sales_invoice",
                    source_doctype: "Shipping Document",
                    target: cur_frm,
                    setters: {
                        customer: cur_frm.doc.customer || undefined,
                    },
                    get_query_filters: {
                        docstatus: 1,
                        status: ["!=", "Closed"],
                        per_billed: ["<", 99.99],
                        company: cur_frm.doc.company
                    }
                })
            }, __("Get items from"));
        }
    },
    before_save: function (frm) {
        frm.events.cal_igst_amount(frm);
        if (frm.doc.shipping_address_name == "") {
            frm.set_value("shipping_address_name", frm.doc.customer_address);
        }
        frappe.db.get_value("Company", frm.doc.company, 'abbr', function (r) {
            if (frm.doc.is_opening == "Yes") {
                $.each(frm.doc.items || [], function (i, d) {
                    d.income_account = 'Temporary Opening - ' + r.abbr;
                });
            }
        });

        frm.doc.items.forEach(function (d) {

            if (in_list["32041610", "32041610", "32041610"], d.gst_hsn_code) {
                frappe.model.set_value(d.doctype, d.name, 'meis_rate', '3');
            }
            else {
                frappe.model.set_value(d.doctype, d.name, 'meis_rate', '5');
            }
            frappe.call({
                method: 'evergreen.api.get_customer_ref_code',
                args: {
                    'item_code': d.item_code,
                    'customer': frm.doc.customer,
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.model.set_value(d.doctype, d.name, 'item_name', r.message);
                        //frappe.model.set_value(d.doctype, d.name, 'description', r.message);
                    }
                }
            })
/*             frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
                if (r.country != "India") {
                    frappe.model.set_value(d.doctype, d.name, "fob_value", flt(d.base_amount - d.freight - d.insurance));
                }
            }) */
        });
        frm.refresh_field('items');
        frm.trigger("cal_total");
        frm.trigger('calculate_total_fob_value');
        frm.trigger("duty_drawback_cal");
        frm.trigger("box_cal");
        frm.trigger("define_custom_name");


    },
	/* conversion_rate: function(frm){
		frm.doc.items.forEach(function(d){
			if(frm.doc.currency != "INR"){
				frappe.model.set_value(cdt, cdn, "fob_value", flt(d.base_amount - d.freight - d.insurance));
			}
		});
	}, */
    customer: function (frm) {
        frappe.call({
            method: "evergreen.api.get_custom_address",
            args: {
                party: frm.doc.customer,
                party_type: "Customer"
            },
            callback: function (r) {
                if (r.message) {
                    frm.set_value("custom_address", r.message.customer_address);
                    frm.set_value("custom_address_display", r.message.address_display);
                }
            }
        });
    },
    notify_party: function (frm) {
        if (cur_frm.doc.notify_party) {
            return frappe.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {
                    "address_dict": frm.doc.notify_party
                },
                callback: function (r) {
                    if (r.message)
                        frm.set_value("notify_address_display", r.message);
                }
            });
        }
    },
    custom_consignee_address: function (frm) {
        if (cur_frm.doc.custom_address) {
            return frappe.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {
                    "address_dict": frm.doc.custom_consignee_address
                },
                callback: function (r) {
                    if (r.message) {

                        frm.set_value("custom_consignee_address_display", r.message);
                    }
                }
            });
        }
    },
    custom_address: function (frm) {
        if (cur_frm.doc.custom_address) {
            return frappe.call({
                method: "frappe.contacts.doctype.address.address.get_address_display",
                args: {
                    "address_dict": frm.doc.custom_address
                },
                callback: function (r) {
                    if (r.message) {

                        frm.set_value("custom_address_display", r.message);
                    }
                }
            });
        }
    },
    
    cal_total: function (frm) {
        let total_qty = 0.0;
        let total_packages = 0;
        let total_net_wt = 0.0;
        let total_gr_wt = 0.0;
        let total_tare_wt = 0.0;
        let total_pallets = 0;
        let total_meis = 0.0;

        frm.doc.items.forEach(function (d) {
            //frappe.model.set_value(d.doctype, d.name, 'gross_wt', (d.tare_wt + d.qty));
            total_qty += flt(d.qty);
            total_packages += flt(d.no_of_packages);
            total_net_wt += flt(d.net_wt);
            d.total_tare_weight = flt(d.tare_wt * d.no_of_packages);
            d.gross_wt = flt(d.total_tare_weight) + flt(d.qty);
            total_tare_wt += flt(d.total_tare_weight);
            total_gr_wt += flt(d.gross_wt);
            total_pallets += flt(d.total_pallets);
            frappe.model.set_value(d.doctype, d.name, "meis_value", flt(d.fob_value * d.meis_rate / 100.0));
            total_meis += flt(d.meis_value);
            frappe.model.set_value(d.doctype, d.name, "capped_amount", flt(d.qty * d.capped_rate));
        });
        frm.set_value("total_qty", total_qty);
        frm.set_value("total_packages", total_packages);
        frm.set_value("total_nt_wt", total_net_wt);
        frm.set_value("total_gr_wt", total_gr_wt);
        frm.set_value("total_tare_wt", total_tare_wt);
        frm.set_value("total_pallets", total_pallets);
        frm.set_value("total_meis", total_meis);
    },
    cal_igst_amount: function (frm) {
        let total_igst = 0.0;
        frm.doc.items.forEach(function (d) {
            if (d.igst_rate) {
                frappe.model.set_value(d.doctype, d.name, 'igst_amount', d.base_amount * parseInt(d.igst_rate) / 100);
            } else {
                frappe.model.set_value(d.doctype, d.name, 'igst_amount', 0.0);
            }
            total_igst += flt(d.igst_amount);
        });
        frm.set_value('total_igst_amount', total_igst);
    },
    duty_drawback_cal: function (frm) {
        let total_dt = 0;
        frm.doc.items.forEach(function (d) {
            let duty_drawback_amount = 0.0
            if (d.maximum_cap){
                duty_drawback_amount = Math.min(flt(d.fob_value * d.duty_drawback_rate / 100),d.capped_amount)     
            }
            else {
                duty_drawback_amount = flt(d.fob_value * d.duty_drawback_rate / 100)
            }
            frappe.model.set_value(d.doctype, d.name, "duty_drawback_amount", duty_drawback_amount);
            total_dt += flt(d.duty_drawback_amount);
        });
        frm.set_value("total_duty_drawback", total_dt);
    },
    calculate_total_fob_value: function (frm) {
        let total_fob_value = 0;
        frm.doc.items.forEach(function (d) {
            total_fob_value += flt(d.fob_value);
        });
        frm.set_value("total_fob_value", total_fob_value)
        //frm.set_value("total_fob_value", flt(total_fob_value - (frm.doc.freight * frm.doc.conversion_rate) - (frm.doc.insurance * frm.doc.conversion_rate)));
    },
    box_cal: function (frm) {
        frm.doc.items.forEach(function (d, i) {
            if (i == 0) {
                d.packages_from = 1;
                d.packages_to = d.no_of_packages;
            }
            else {
                d.packages_from = Math.round(frm.doc.items[i - 1].packages_to + 1);
                d.packages_to = Math.round(d.packages_from + d.no_of_packages - 1);
            }
        });
        frm.refresh_field('items');
    },
    pallet_cal: function (frm) {
        frm.doc.items.forEach(function (d, i) {
            if (d.palleted) {
                if (i == 0) {
                    d.pallet_no_from = 1;
                    d.pallet_no_to = Math.round(d.total_pallets);
                }
                else {
                    d.pallet_no_from = Math.round(frm.doc.items[i - 1].pallet_no_to + 1);
                    d.pallet_no_to = Math.round(d.pallet_no_from + d.total_pallets - 1);
                }
            }
        });
        frm.refresh_field('items');
    },
    define_custom_name: function (frm) {
        frm.doc.items.forEach(function (d) {
            if (d.gst_hsn_code == '32041610') {
                frappe.model.set_value(d.doctype, d.name, "item_custom_name", "REACTIVE YELLOW");
            }
            else if (d.gst_hsn_code == '32041620') {
                frappe.model.set_value(d.doctype, d.name, "item_custom_name", "REACTIVE ORANGE");
            }
            else if (d.gst_hsn_code == '32041630') {
                frappe.model.set_value(d.doctype, d.name, "item_custom_name", "REACTIVE RED");
            }
            else if (d.gst_hsn_code == '32041640') {
                frappe.model.set_value(d.doctype, d.name, "item_custom_name", "REACTIVE VIOLET");
            }
            else if (d.gst_hsn_code == '32041650') {
                frappe.model.set_value(d.doctype, d.name, "item_custom_name", "REACTIVE BLUE");
            }
            else if (d.gst_hsn_code == '32041660') {
                frappe.model.set_value(d.doctype, d.name, "item_custom_name", "REACTIVE GREEN");
            }
            else if (d.gst_hsn_code == '32041670') {
                frappe.model.set_value(d.doctype, d.name, "item_custom_name", "REACTIVE BROWN");
            }
            else if (d.gst_hsn_code == '32041680') {
                frappe.model.set_value(d.doctype, d.name, "item_custom_name", "REACTIVE BLACK");
            }
            else {
                frappe.model.set_value(d.doctype, d.name, "item_custom_name", "REACTIVE DYES");
            }
        });
    }
});

frappe.ui.form.on("Sales Invoice Item", {
    item_code: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        setTimeout(function () {
            frappe.db.get_value("Batch", d.batch_no, ['packaging_material', 'packing_size', 'lot_no', 'batch_yield', 'concentration'], function (r) {
                frappe.model.set_value(cdt, cdn, 'packaging_material', r.packaging_material);
                frappe.model.set_value(cdt, cdn, 'packing_size', r.packing_size);
                frappe.model.set_value(cdt, cdn, 'lot_no', r.lot_no);
                frappe.model.set_value(cdt, cdn, 'batch_yield', r.batch_yield);
                frappe.model.set_value(cdt, cdn, 'concentration', r.concentration);
            })
        }, 1000)
    },
    qty: function (frm, cdt, cdn) {
        // frm.events.cal_total(frm);
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value", flt(d.base_amount - d.freight - d.insurance));
            }
        })
        frappe.model.set_value(cdt, cdn, "no_of_packages", flt(d.qty / d.packed_in));
        frappe.model.set_value(cdt, cdn, "total_pallets", Math.round(d.qty / d.pallet_size));
    },

    base_amount: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value", flt(d.base_amount - d.freight - d.insurance));
            }
        })
    },
    freight: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value", flt(d.base_amount - d.freight - d.insurance));
            }
        })
    },
    insurance: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.db.get_value("Address", frm.doc.customer_address, 'country', function (r) {
            if (r.country != "India") {
                frappe.model.set_value(cdt, cdn, "fob_value", flt(d.base_amount - d.freight - d.insurance));
            }
        })
    },
    duty_drawback_rate: function (frm, cdt, cdn) {
        frm.events.duty_drawback_cal(frm);
    },
    capped_rate: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "capped_amount", flt(d.qty * d.capped_rate));
    },
    capped_amount: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        if (d.maximum_cap == 1) {
            if (d.capped_amount < d.duty_drawback_amount) {
                frappe.model.set_value(cdt, cdn, "duty_drawback_amount", d.capped_amount);
            }
            if (d.fob_value) {
                frappe.model.set_value(cdt, cdn, "effective_rate", flt(d.capped_amount / d.fob_value * 100));
            }
        }
    },

    meis_rate: function (frm, cdt, cdn) {
        frm.events.cal_total(frm);
    },

    fob_value: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        frm.events.duty_drawback_cal(frm);
        frm.events.calculate_total_fob_value(frm);
        frm.events.cal_igst_amount(frm);
        //frappe.model.set_value(cdt, cdn, "igst_taxable_value", d.fob_value);
    },

	/* igst_taxable_value: function(frm, cdt, cdn){
		frm.events.cal_igst_amount(frm);
	}, */

    igst_rate: function (frm, cdt, cdn) {
        frm.events.cal_igst_amount(frm);
    },
    packaging_material: function (frm, cdt, cdn) {
        let d = locals[cdt][cdn];
        if (d.packaging_material == "Box") {
            frappe.model.set_value(cdt, cdn, "tare_wt", "1.5");
        }
        else if (d.packaging_material == "Jumbo Bag") {
            frappe.model.set_value(cdt, cdn, "tare_wt", "2.5");
        }
        else if (d.packaging_material == "Drum") {
            frappe.model.set_value(cdt, cdn, "tare_wt", "17.5");
        }
    },
    packed_in: function (frm, cdt, cdn) {
        // frm.events.cal_total(frm);
        let d = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "no_of_packages", flt(d.qty / d.packed_in));
    },
    pallet_size: function (frm, cdt, cdn) {
        frappe.run_serially([
            () => {
                let d = locals[cdt][cdn];
                frappe.model.set_value(cdt, cdn, "total_pallets", Math.round(d.qty / d.pallet_size));
            },
            () => {
                frm.events.pallet_cal(frm);
            }
        ]);
    },
    no_of_packages: function (frm, cdt, cdn) {
        frm.events.box_cal(frm);
    },
});


erpnext.accounts.SalesInvoiceController = erpnext.accounts.SalesInvoiceController.extend({
    payment_terms_template: function() {
		var me = this;
        const doc = me.frm.doc;
		if(doc.payment_terms_template && doc.doctype !== 'Delivery Note') {
            if (frappe.meta.get_docfield("Sales Invoice", "bl_date") || frappe.meta.get_docfield("Sales Invoice", "shipping_bill_date")){
                var posting_date = doc.bl_date || doc.shipping_bill_date || doc.posting_date || doc.transaction_date;
            }
            else{
                var posting_date =  doc.posting_date || doc.transaction_date;
            }

			frappe.call({
				method: "erpnext.controllers.accounts_controller.get_payment_terms",
				args: {
					terms_template: doc.payment_terms_template,
					posting_date: posting_date,
					grand_total: doc.rounded_total || doc.grand_total,
					bill_date: doc.bill_date
				},
				callback: function(r) {
					if(r.message && !r.exc) {
						me.frm.set_value("payment_schedule", r.message);
					}
				}
			})
		}
    },
    onload:function(){
        var me = this;
        
        this.frm.set_query("batch_no", "items", function (doc, cdt, cdn) {
            let d = locals[cdt][cdn];
            if (!d.item_code) {
                frappe.throw(__("Please enter Item Code to get batch no"));
            }
            else if(d.item_group == "Raw Material"){
                return {
                    query: "evergreen.batch_valuation.get_batch_no",
                    filters: {
                        'item_code': d.item_code,
                        'warehouse': d.warehouse
                    }
                }
            }
            else {
                return {
                    query: "evergreen.batch_valuation.get_batch_no",
                    filters: {
                        'item_code': d.item_code,
                        'warehouse': d.warehouse,
                        'customer': doc.customer
                    }
                }
            }
        });
        this.frm.set_query("item_code", "items", function () {
            return {
                query: "evergreen.api.new_item_query",
                filters: {
                    'is_sales_item': 1
                }
            }
        });
    }
})

$.extend(cur_frm.cscript, new erpnext.accounts.SalesInvoiceController({ frm: cur_frm }));
