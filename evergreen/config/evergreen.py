from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Courier"),
			"items": [
				{
					"type": "doctype",
					"name": "Courier Agency",
				},
				{
					"type": "doctype",
					"name": "Courier Items",
				},
			]
		},
		{
			"label": _("Inward"),
			"items": [
				{
					"type": "doctype",
					"name": "Inward Tracking",
				},
				{
					"type": "doctype",
					"name": "Inward Sample",
				},
			]
		},
		{
			"label": _("Labour"),
			"items": [
				{
					"type": "doctype",
					"name": "Labour",
				},
				{
					"type": "doctype",
					"name": "Labour Advance Payment",
				},
				{
					"type": "doctype",
					"name": "Labour Attendance Tool"
				},
				{
					"type": "doctype",
					"name": "Labour Payroll"
				},
			]
		},
		{
			"label": _("Outward"),
			"items": [
				{
					"type": "doctype",
					"name": "Outward Tracking",
				},
				{
					"type": "doctype",
					"name": "Outward Sample",
				},
				{
					"type": "doctype",
					"name": "Outward Sample Print"
				},
				{
					"type": "doctype",
					"name": "Price Calculation",
				},
			]
		},
		{
			"label": _("Other"),
			"items": [
				{
					"type": "doctype",
					"name": "Purchase Price",
				},
				{
					"type": "doctype",
					"name": "Ball Mill Data Sheet",
				},
				{
					"type": "doctype",
					"name": "LUT Detail"
				},
			]
		},
		{
			"label": _("Jobwork"),
			"items": [
				{
					"type": "doctype",
					"name": "Jobwork Challan",
				},
			]
		}
	]