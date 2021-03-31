cur_frm.fields_dict.from_warehouse.get_query = function (doc) {
	return {
		filters: {
			"company": doc.company,
            "is_group":0,
		}
	}
};
cur_frm.fields_dict.from_warehouse.get_query = function (doc) {
	return {
		filters: {
			"company": doc.company,
            "is_group":0,
		}
	}
};

cur_frm.fields_dict.items.grid.get_field("s_warehouse").get_query = function (doc) {
	return {
		filters: {
			"company": doc.company,
            "is_group":0,
		}
	}
};
cur_frm.fields_dict.items.grid.get_field("t_warehouse").get_query = function (doc) {
	return {
		filters: {
			"company": doc.company,
            "is_group":0,
		}
	}
};