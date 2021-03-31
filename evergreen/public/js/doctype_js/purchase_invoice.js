cur_frm.fields_dict.taxes_and_charges.get_query = function(doc) {
	return {
		filters: {
			"company": doc.company
		}
	}
};