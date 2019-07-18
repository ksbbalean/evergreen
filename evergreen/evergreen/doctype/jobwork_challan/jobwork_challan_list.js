frappe.listview_settings['Jobwork Challan'] = {
	add_fields: ["status"],
	get_indicator: function(doc) {
		return [__(doc.status), {
			"Draft": "red",
			"Sent": "blue",
			"Partially Received": "orange",
			"Received": "green",
			"Cancelled": "red"
		}[doc.status], "status,=," + doc.status];
	}
};