
var get_geo = function() {

    $('#btn-geo-show').hide();
    $('#geography_map').show();

    $.getJSON('/dashboard/get/geo_stats', function (data) {

        var mapData = Highcharts.geojson(Highcharts.maps['custom/world']);

        // Correct UK to GB in data
        $.each(data, function () {
            if (this.code === 'UK') {
                this.code = 'GB';
            }
        });

	// console.log(data['totals']);

	function numberWithCommas(x) {
	    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
	}

	var table = $('#geo_totals').DataTable({
	    "paging":   false,
	    "ordering": false,
	    "info":     false,
	    "searching":    false,
	    "data": [ data['totals'] ],
	    "columns" : [ {'data': 'nregistered', 'title': "Total # ever registered", "class": "dt-center" },
			  {'data': 'nviewed', 'title': "Total # viewed", "class": "dt-center" },
			  {'data': 'nexplored', 'title': "Total # explored", "class": "dt-center" },
			  {'data': 'ncertified', 'title': "Total # certified", "class": "dt-center" },
			  {'data': 'nverified', 'title': "Total # verified-ID", "class": "dt-center" },
			  ],
	    "columnDefs": [
		{
		    "targets": [ 0, 1, 2, 3, 4 ],
                    "render": function ( data, type, row ) {
			return numberWithCommas(data);   // (eval(data)).toFixed(2);
                    },
		}
	    ],
        });

    $('#geo_totals tbody tr').each( function() {
        var nTds = $('td', this);
	nTds[0].setAttribute('title', 'Ever registered does not subtract those who un-register');
	nTds[1].setAttribute('title', 'Viewed = visited the course registered for, at least once');
	nTds[2].setAttribute('title', 'Explored = visited at least half the chapters of the course');
	nTds[3].setAttribute('title', 'Certified = earned a certificate in the course');
	nTds[4].setAttribute('title', 'Verified-ID = signed up for a paid verified-ID track');
	nTds.tooltip();
    });

	var table = $('#geo_top').DataTable({
            dom: 'T<"clear">lfrtip',
	    "paging":   true,
	    "ordering": true,
	    "info":     true,
	    "searching":    true,
            "order": [ 1, 'desc' ],
	    "data": data['table'],
	    "columns" : [ {'data': 'countryLabel', 'title': "Country Name", "class": "dt-center" },
			  {'data': 'nregistered', 'title': "# registered", "class": "dt-center" },
			  {'data': 'nviewed', 'title': "# viewed", "class": "dt-center" },
			  {'data': 'nexplored', 'title': "# explored", "class": "dt-center" },
			  {'data': 'ncertified', 'title': "# certified", "class": "dt-center" },
			  {'data': 'cert_pct', 'title': "% certified (of registered)", "class": "dt-center" },
			  {'data': 'cert_pct_of_viewed', 'title': "% certified (of viewed)", "class": "dt-center" },
			  // {'data': 'avg_hours_certified', 'title': "avg hours spent on course (certified)", "class": "dt-center" },
			  {'data': 'nverified', 'title': "# verified id", "class": "dt-center" },
			  {'data': 'ncert_verified', 'title': "# verified id certified", "class": "dt-center" },
			  {'data': 'verified_cert_pct', 'title': "% certified (of verified)", "class": "dt-center" },
			  ],
	    "columnDefs": [
		{
		    "targets": [ 1,2,3,4, 7, 8 ],
                    "render": function ( data, type, row ) {
			return numberWithCommas(data);   // (eval(data)).toFixed(2);
                    },
		}
	    ],
        });

    var update_tooltips = function(){
	$('#geo_top tbody tr').each( function() {
            var sTitle;
            var nTds = $('td', this);
            var country = $(nTds[0]).text();
            var registered = $(nTds[1]).text();
            var certified = $(nTds[4]).text();
            var verified = $(nTds[8]).text();
	    var rpct = ((Number(registered.replace(',','')) / Number(data['totals']['nregistered'])) * 100.0).toFixed(2);
	    var vpct = ((Number(verified.replace(',','')) / Number(data['totals']['nverified'])) * 100.0).toFixed(2);
            sTitle = "<table><tr><th colspan='3'>" + country + "</th></tr>";
	    sTitle += "<tr><td># registered</td><td>" + registered + "</td><td>" + rpct +"% of total</td></tr>";
	    sTitle += "<tr><td># verified</td><td>" + verified + "</td><td>" + vpct +"% of total</td></tr>";
	    sTitle += "</table>";
            this.setAttribute( 'title', sTitle );
	} );
    };
	
    update_tooltips();

    $('#geo_top').on( 'draw.dt', function () {     
	update_tooltips();
    });

    /* Apply the tooltips */
    table.$('tr').tooltip( {
        'content': function () {   return $(this).prop('title'); },
	'html': true,
        "delay": 0,
        // "track": true,
        // "fade": 250
    } );

	// console.log(data['series'])

        $('#geomap').highcharts('Map', {
            chart : {
                borderWidth : 1
            },

            title: {
                text: 'Enrollment and certification by country (updated ' + data['last_updated']  + ')'
            },
	    credits: {  enabled: false  },

            subtitle : {
                text : 'Bubble size is proportional to registration'
            },

            legend: {
                enabled: false
            },

            mapNavigation: {
                enabled: true,
                buttonOptions: {
                    verticalAlign: 'bottom'
                }
            },

            series : [{
                name: 'Countries',
                mapData: mapData,
                color: '#E0E0E0',
                enableMouseTracking: false
            }, {
                type: 'mapbubble',
                mapData: mapData,
                name: 'Registration and Certification',
                joinBy: ['iso-a2', 'cc'],
                data: data['series'],
                minSize: 4,
                maxSize: '12%',
                tooltip: {
                    pointFormat: '{point.cc}:  {point.name}<br/>{point.z} registered<br/>{point.ncertified} certified<br/>{point.cert_pct} certification %'
                }
            }]
        });

    });

    $('[data-spy="scroll"]').each(function () {
	var $spy = $(this).scrollspy('refresh')
    });
};

$('#btn-geo-show').click(get_geo);

