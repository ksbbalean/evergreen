// Copyright (c) 2019, Finbyz Tech Pvt Ltd and contributors
// For license information, please see license.txt

frappe.provide("erpnext.stock");

this.frm.add_fetch('batch_no', 'lot_no', 'lot_no');
this.frm.add_fetch('batch_no', 'packaging_material', 'packaging_material');
this.frm.add_fetch('batch_no', 'packing_size', 'packing_size');
this.frm.add_fetch('batch_no', 'batch_yield', 'batch_yield');
this.frm.add_fetch('batch_no', 'concentration', 'concentration');

frappe.ui.form.on('Material Transfer Instruction', {
	setup: function(frm) {
		frm.set_query('work_order', function() {
			return {
				filters: [
					['Work Order', 'docstatus', '=', 1],
					['Work Order', 'qty', '>','`tabWork Order`.produced_qty'],
					['Work Order', 'company', '=', frm.doc.company]
				]
			}
		});

		frappe.db.get_value('Stock Settings', {name: 'Stock Settings'}, 'sample_retention_warehouse', (r) => {
			if (r.sample_retention_warehouse) {
				var filters = [
							["Warehouse", 'company', '=', frm.doc.company],
							["Warehouse", "is_group", "=",0],
							['Warehouse', 'name', '!=', r.sample_retention_warehouse]
						]
				frm.set_query("from_warehouse", function() {
					return {
						filters: filters
					};
				});
				frm.set_query("s_warehouse", "items", function() {
					return {
						filters: filters
					};
				});
			}
		});

		frm.set_query('batch_no', 'items', function(doc, cdt, cdn) {
			var item = locals[cdt][cdn];
			if(!item.item_code) {
				frappe.throw(__("Please enter Item Code to get Batch Number"));
			} else {
				var filters = {
					'item_code': item.item_code,
					'posting_date': frm.doc.posting_date || frappe.datetime.nowdate()
				}

				if(item.s_warehouse) filters["warehouse"] = item.s_warehouse;
				return {
					query : "evergreen.batch_valuation.get_batch_no",
					filters: filters
				}
			}
		});
	},

	refresh: function(frm) {

	},

	company: function(frm) {
		if(frm.doc.company) {
			var company_doc = frappe.get_doc(":Company", frm.doc.company);
			if(company_doc.default_letter_head) {
				frm.set_value("letter_head", company_doc.default_letter_head);
			}
			frm.trigger("toggle_display_account_head");
		}
	},

	set_serial_no: function(frm, cdt, cdn, callback) {
		var d = frappe.model.get_doc(cdt, cdn);
		if(!d.item_code && !d.s_warehouse && !d.qty) return;
		var	args = {
			'item_code'	: d.item_code,
			'warehouse'	: cstr(d.s_warehouse),
			'stock_qty'		: d.transfer_qty
		};
		frappe.call({
			method: "erpnext.stock.get_item_details.get_serial_no",
			args: {"args": args},
			callback: function(r) {
				if (!r.exe){
					frappe.model.set_value(cdt, cdn, "serial_no", r.message);
				}

				if (callback) {
					callback();
				}
			}
		});
	},

	set_basic_rate: function(frm, cdt, cdn) {
		const item = locals[cdt][cdn];
		item.transfer_qty = flt(item.qty) * flt(item.conversion_factor);

		const args = {
			'item_code'			: item.item_code,
			'posting_date'		: frm.doc.posting_date,
			'posting_time'		: frm.doc.posting_time,
			'warehouse'			: cstr(item.s_warehouse),
			'serial_no'			: item.serial_no,
			'company'			: frm.doc.company,
			'qty'				: item.s_warehouse ? -1*flt(item.transfer_qty) : flt(item.transfer_qty),
			'voucher_type'		: frm.doc.doctype,
			'voucher_no'		: item.name,
			'allow_zero_valuation': 1,
			'batch_no'			: item.batch_no || ''
		};

		if (item.item_code || item.serial_no) {
			frappe.call({
				method: "erpnext.stock.utils.get_incoming_rate",
				args: {
					args: args
				},
				callback: function(r) {
					frappe.model.set_value(cdt, cdn, 'basic_rate', (r.message || 0.0));
					frm.events.calculate_basic_amount(frm, item);
				}
			});
		}
	},

	get_warehouse_details: function(frm, cdt, cdn) {
		var child = locals[cdt][cdn];
		if(!child.bom_no) {
			frappe.call({
				method: "evergreen.evergreen.doctype.material_transfer_instruction.material_transfer_instruction.get_warehouse_details",
				args: {
					"args": {
						'item_code': child.item_code,
						'warehouse': cstr(child.s_warehouse),
						'transfer_qty': child.transfer_qty,
						'serial_no': child.serial_no,
						'qty': child.s_warehouse ? -1* child.transfer_qty : child.transfer_qty,
						'posting_date': frm.doc.posting_date,
						'posting_time': frm.doc.posting_time,
						'company': frm.doc.company,
						'voucher_type': frm.doc.doctype,
						'voucher_no': child.name,
						'allow_zero_valuation': 1
					}
				},
				callback: function(r) {
					if (!r.exc) {
						$.extend(child, r.message);
						frm.events.calculate_basic_amount(frm, child);
					}
				}
			});
		}
	},

	calculate_basic_amount: function(frm, item) {
		item.basic_amount = flt(flt(item.transfer_qty) * flt(item.basic_rate),
			precision("basic_amount", item));

		frm.events.calculate_amount(frm);
	},

	calculate_amount: function(frm) {
		// frm.events.calculate_total_additional_costs(frm);

		for (let i in frm.doc.items) {
			let item = frm.doc.items[i];

			item.amount = flt(item.basic_amount, precision("amount", item));

			item.valuation_rate = flt(item.basic_rate, precision("valuation_rate", item));
		}

		refresh_field('items');
	},
});

frappe.ui.form.on('Material Transfer Instruction Detail', {
	qty: function(frm, cdt, cdn) {
		frm.events.set_serial_no(frm, cdt, cdn, () => {
			frm.events.set_basic_rate(frm, cdt, cdn);
		});
	},

	conversion_factor: function(frm, cdt, cdn) {
		frm.events.set_basic_rate(frm, cdt, cdn);
	},

	s_warehouse: function(frm, cdt, cdn) {
		frm.events.set_serial_no(frm, cdt, cdn, () => {
			frm.events.get_warehouse_details(frm, cdt, cdn);
		});
	},

	basic_rate: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		frm.events.calculate_basic_amount(frm, item);
	},

	barcode: function(doc, cdt, cdn) {
		var d = locals[cdt][cdn];
		if (d.barcode) {
			frappe.call({
				method: "erpnext.stock.get_item_details.get_item_code",
				args: {"barcode": d.barcode },
				callback: function(r) {
					if (!r.exe){
						frappe.model.set_value(cdt, cdn, "item_code", r.message);
					}
				}
			});
		}
	},

	uom: function(doc, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.uom && d.item_code){
			return frappe.call({
				method: "evergreen.evergreen.doctype.material_transfer_instruction.material_transfer_instruction.get_uom_details",
				args: {
					item_code: d.item_code,
					uom: d.uom,
					qty: d.qty
				},
				callback: function(r) {
					if(r.message) {
						frappe.model.set_value(cdt, cdn, r.message);
					}
				}
			});
		}
	},

	item_code: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if(d.item_code) {
			var args = {
				'item_code'			: d.item_code,
				'warehouse'			: cstr(d.s_warehouse),
				'transfer_qty'		: d.transfer_qty,
				'serial_no'		: d.serial_no,
				'bom_no'		: d.bom_no,
				'company'		: frm.doc.company,
				'qty'			: d.qty,
				'voucher_type'		: frm.doc.doctype,
				'voucher_no'		: d.name,
				'allow_zero_valuation': 1,
			};
			return frappe.call({
				doc: frm.doc,
				method: "get_item_details",
				args: args,
				callback: function(r) {
					if(r.message) {
						var d = locals[cdt][cdn];
						$.each(r.message, function(k, v) {
							d[k] = v;
						});
						refresh_field("items");
						erpnext.stock.select_batch_and_serial_no(frm, d);
					}
				}
			});
		}
	},
});

erpnext.stock.MaterialTransferInstruction = erpnext.stock.StockController.extend({
	setup: function() {
		var me = this;

		this.setup_posting_date_time_check();

		this.frm.fields_dict.bom_no.get_query = function() {
			return {
				filters:{
					"docstatus": 1,
					"is_active": 1
				}
			};
		};

		this.frm.fields_dict.items.grid.get_field('item_code').get_query = function() {
			return erpnext.queries.item({is_stock_item: 1});
		};

		this.frm.set_indicator_formatter('item_code',
			function(doc) {
				if (!doc.s_warehouse) {
					return 'blue';
				} else {
					return (doc.qty<=doc.actual_qty) ? "green" : "orange"
				}
			})
	},

	onload_post_render: function() {
		var me = this;

		if(me.frm.doc.__islocal && me.frm.doc.company && !me.frm.doc.amended_from) {
			me.frm.trigger("company");
		}
		// if(!this.item_selector && false) {
		// 	this.item_selector = new erpnext.ItemSelector({frm: this.frm});
		// }
	},

	refresh: function() {
		var me = this;
		this.toggle_enable_bom();
		erpnext.hide_company();
		erpnext.utils.add_item(this.frm);
	},

	on_submit: function() {
		this.clean_up();
	},

	after_cancel: function() {
		this.clean_up();
	},

	clean_up: function() {
		// Clear Work Order record from locals, because it is updated via Stock Entry
		if(this.frm.doc.work_order &&
				in_list(["Manufacture", "Material Transfer for Manufacture"], this.frm.doc.purpose)) {
			frappe.model.remove_from_locals("Work Order",
				this.frm.doc.work_order);
		}
	},

	get_items: function() {
		var me = this;
		if(!this.frm.doc.fg_completed_qty || !this.frm.doc.bom_no)
			frappe.throw(__("BOM and Manufacturing Quantity are required"));

		if(this.frm.doc.work_order || this.frm.doc.bom_no) {
			// if Work Order / bom is mentioned, get items
			return this.frm.call({
				doc: me.frm.doc,
				method: "get_items",
				callback: function(r) {
					if(!r.exc) refresh_field("items");
				}
			});
		}
	},

	work_order: function() {
		var me = this;
		this.toggle_enable_bom();
		if(!me.frm.doc.work_order) {
			return;
		}

		return frappe.call({
			method: "evergreen.evergreen.doctype.material_transfer_instruction.material_transfer_instruction.get_work_order_details",
			args: {
				work_order: me.frm.doc.work_order
			},
			callback: function(r) {
				if (!r.exc) {
					$.each(["from_bom", "bom_no", "fg_completed_qty", "use_multi_level_bom"], function(i, field) {
						me.frm.set_value(field, r.message[field]);
					})

					me.get_items()
				}
			}
		});
	},

	toggle_enable_bom: function() {
		this.frm.toggle_enable("bom_no", !!!this.frm.doc.work_order);
	},

	items_add: function(doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);

		if(!row.s_warehouse) row.s_warehouse = this.frm.doc.from_warehouse;
	},

	items_on_form_rendered: function(doc, grid_row) {
		erpnext.setup_serial_no();
	},
});

erpnext.stock.select_batch_and_serial_no = (frm, item) => {
	let get_warehouse_type_and_name = (item) => {
		let value = '';
		value = cstr(item.s_warehouse) || '';
		return {
			type: 'Source Warehouse',
			name: value
		};
	}

	frappe.require("assets/erpnext/js/utils/serial_no_batch_selector.js", function() {
		new erpnext.SerialNoBatchSelector({
			frm: frm,
			item: item,
			warehouse_details: get_warehouse_type_and_name(item),
		});
	});
}

$.extend(cur_frm.cscript, new erpnext.stock.MaterialTransferInstruction({frm: cur_frm}));
