parameters = {{parameters}};
parameters.get_table_columns = true;

$.getJSON(
    '/custom/get_report_data/{{report_name}}', 
    parameters,
    
    function(data) {
	
	html = '<table id="table-{{report_name}}" class="display" width="100%"></table>';
	html += '<div id="plot-{{report_name}}"></div>';
	if (data.error){
            html = "Error!  " + data.error;
        }
	$('#contain-{{report_name}}').html(html);
      	if (data.error){ return; }

	// make data table
	var table = $('#table-{{report_name}}').DataTable({
	    dom: 'T<"clear">lfrtip',
	    "columns": data['tablecolumns'],
	    "pageLength": 10,
	    searching: true,
	    ordering: true,
	    data: data['data'],
	});
	
	// create data series
	var series = [];
	data['data'].forEach(function(x){
	    srow = {cc: x.cc,
		    z: Number(x.nverified),
		    name: x.countryLabel,
		   };
	    series.push(srow);
	});
	
	
	// plot data
	$('#plot-{{report_name}}').highcharts({
	    
	    chart: { type: 'spline',  zoomType: 'x' },
	    rangeSelector : {
		selected : 5
	    },
	    credits: {  enabled: false  },
	    title : {
		text : 'Plot title',
	    },
	    
	    xAxis: {
		type: 'datetime',
		dateTimeLabelFormats: { // don't display the dummy year
		    month: '%e. %b',
		    year: '%b'
		},
		title: {
		    text: 'Date'
		}
	    },
	    
	    series : series,
	});      
	
    } );
