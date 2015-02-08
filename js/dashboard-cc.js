
var cc_data = {};

var cc_forum_show = function(){
    
    var ccfhtml = '<h3>Forum and Navigation events stats</h3><table id="cc_forum_table"></table>'
    $('#cc_forum').html(ccfhtml);

    var data = cc_data['data'];

    var cc_forum_table = $('#cc_forum_table').DataTable({
            dom: 'T<"clear">lfrtip',
	    "paging":   true,
	    "ordering": true,
	    "info":     true,
	    "searching":    true,
            "order": [ 1, 'desc' ],
	    "data": data['table'],
            scrollY:        false,
            scrollX:        true,
            scrollCollapse: true,
	    // "columns" : data['tablecolumns'],
	    'columns': [{"title": "course_id", "class": "dt-center", "data": "course_id"}, 
			{"title": "nforum_posts_sum", "class": "dt-center", "data": "nforum_posts_sum"},
			{"title": "min_gade_certified", "class": "dt-center", "data": "min_gade_certified"},
			{"title": "nforum_votes_sum", "class": "dt-center", "data": "nforum_votes_sum"},
			{"title": "nforum_endorsed_sum", "class": "dt-center", "data": "nforum_endorsed_sum"},
			{"title": "nforum_threads_sum", "class": "dt-center", "data": "nforum_threads_sum"},
			{"title": "nforum_commments_sum", "class": "dt-center", "data": "nforum_commments_sum"},
			{"title": "nforum_pinned_sum", "class": "dt-center", "data": "nforum_pinned_sum"},
			{"title": "nprogcheck_avg", "class": "dt-center", "data": "nprogcheck_avg"},
			{"title": "certified_nprogcheck", "class": "dt-center", "data": "certified_nprogcheck"},
			{"title": "verified_nprogcheck", "class": "dt-center", "data": "verified_nprogcheck"},
			{"title": "nshow_answer_sum", "class": "dt-center", "data": "nshow_answer_sum"},
			{"title": "nseq_goto_sum", "class": "dt-center", "data": "nseq_goto_sum"},
		       ],
        });
	new $.fn.dataTable.FixedColumns( cc_forum_table );
};

var cc_time_show = function(){
    
    var ccfhtml = '<h3>Time and Video events stats</h3><table id="cc_time_table"></table>'
    $('#cc_time').html(ccfhtml);

    var data = cc_data['data'];

    var cc_time_table = $('#cc_time_table').DataTable({
            dom: 'T<"clear">lfrtip',
	    "paging":   true,
	    "ordering": true,
	    "info":     true,
	    "searching":    true,
            "order": [ 1, 'desc' ],
	    "data": data['table'],
            scrollY:        false,
            scrollX:        true,
            scrollCollapse: true,
	    // "columns" : data['tablecolumns'],
	    'columns': [{"title": "course_id", "class": "dt-center", "data": "course_id"}, 
		        {"title": "nplay_video_sum", "class": "dt-center", "data": "nplay_video_sum"},
			{"title": "nchapters_avg", "class": "dt-center", "data": "nchapters_avg"},
			{"title": "ndays_act_sum", "class": "dt-center", "data": "ndays_act_sum"},
			{"title": "nevents_sum", "class": "dt-center", "data": "nevents_sum"},
			{"title": "min_start_time", "class": "dt-center", "data": "min_start_time"},
			{"title": "max_last_event", "class": "dt-center", "data": "max_last_event"},
			{"title": "max_nchapters", "class": "dt-center", "data": "max_nchapters"},
			{"title": "npause_video_sum", "class": "dt-center", "data": "npause_video_sum"},
			{"title": "avg_of_avg_dt", "class": "dt-center", "data": "avg_of_avg_dt"},
			{"title": "avg_of_sum_dt", "class": "dt-center", "data": "avg_of_sum_dt"},
			{"title": "certified_avg_dt", "class": "dt-center", "data": "certified_avg_dt"},
			{"title": "certified_sum_dt", "class": "dt-center", "data": "certified_sum_dt"},
			{"title": "n_have_ip", "class": "dt-center", "data": "n_have_ip"},
			{"title": "n_missing_cc", "class": "dt-center", "data": "n_missing_cc"},
		       ],
        });
	new $.fn.dataTable.FixedColumns( cc_forum_table );
};

var cc_enrollment_plot = function(){
    $('#cc_enrollment').highcharts({
	chart: { type: 'column',  zoomType: 'x' },
	credits: {  enabled: false  },
	yAxis: {min: 0},
        title : { text : 'Registration by course', },
	subtitle: { text: '(click and drag to zoom)' },
        xAxis: { type: 'category',
		 labels: { rotation: -45, style: { fontSize: '13px', fontFamily: 'Verdana, sans-serif' } }},
        yAxis: {  min: 0,   title: { text: 'Registrants' } },
        legend: { enabled: false },
        tooltip: { pointFormat: 'Registrants: <b>{point.y:.1f}</b>' },
        series : cc_data['data']['enrollment_series'],
    });
}

var cc_certified_plot = function(){
    $('#cc_certified').highcharts({
	chart: { type: 'column',  zoomType: 'x' },
	credits: {  enabled: false  },
	yAxis: {min: 0},
        title : { text : 'Certificate earners by course', },
	subtitle: { text: '(click and drag to zoom)' },
        xAxis: { type: 'category',
		 labels: { rotation: -45, style: { fontSize: '13px', fontFamily: 'Verdana, sans-serif' } }},
        yAxis: {  min: 0,   title: { text: 'Registrants' } },
        legend: { enabled: false },
        tooltip: { pointFormat: 'Certified: <b>{point.y:.1f}</b>' },
        series : cc_data['data']['certified_series'],
    });
}

var cc_verified_plot = function(){
    $('#cc_verified').highcharts({
	chart: { type: 'column',  zoomType: 'x' },
	credits: {  enabled: false  },
	yAxis: {min: 0},
        title : { text : 'ID Verified Registrants by course', },
	subtitle: { text: '(click and drag to zoom)' },
        xAxis: { type: 'category',
		 labels: { rotation: -45, style: { fontSize: '13px', fontFamily: 'Verdana, sans-serif' } }},
        yAxis: {  min: 0,   title: { text: 'ID Verified' } },
        legend: { enabled: false },
        tooltip: { pointFormat: 'ID Verified: <b>{point.y:.1f}</b>' },
        series : cc_data['data']['verified_series'],
    });
}

var cc_all_enrollment_plot = function(){
    // stacked horizontal bar chart, each row one course
    var data = cc_data['data'];
    $('#cc_enrollment').highcharts({
	chart: { type: 'bar',  zoomType: 'x' },
	credits: {  enabled: false  },
	yAxis: {min: 0},
        title : { text : 'Number of registrants by course', },
	subtitle: { text: '(click and drag to zoom)' },
        xAxis: { categories: data['enrollment_courses'] },
        yAxis: {  min: 0,   title: { text: 'Registrants' } },
        legend: {
            reversed: true
        },
        plotOptions: {
            series: {
                stacking: 'normal'
            }
        },
        // tooltip: { pointFormat: 'Registrants: <b>{point.y:.1f}</b>' },
        series : data['all_enrollment_series'],
    });
}

var cc_get_data = function(){
    $.getJSON('/dashboard/get/broad_stats', function (data) {

	var cchtml = '<h3>Enrollment and certification statistics</h3>';
        cchtml += '<div id="cc_enrollment"  style="min-width: 310px; max-width: 800px; height: 1400px; margin: 0 auto"></div><p></p>';
        cchtml += '<div id="cc_certified"></div><p></p>';
        cchtml += '<div id="cc_verified"></div><p></p>';
        cchtml += '<table id="cc_data"></table><p></p>';
	cchtml += '<br style="clear:both;"/>';
	cchtml += "<div>";
        cchtml += '  <div id="cc_forum"><a id="btn-cc-forum-show" class="btn btn-lg btn-primary" href="#" role="button">Show Forum and Navigation event stats »</a></div>';
	cchtml += "  <p></p>";
        cchtml += '  <div id="cc_time"><a id="btn-cc-time-show" class="btn btn-lg btn-primary" href="#" role="button">Show Time and Video event stats »</a></div>';
	cchtml += "  <p></p>";
	cchtml += "</div>";
	cchtml += '<br style="clear:both;"/>';

	$('#cross-course').html(cchtml);

	// console.log('tabledata=', data['table']);
	// console.log('tablecolumns=', data['tablecolumns']);
	
	cc_data['data'] = data;

	$('#btn-cc-forum-show').click(cc_forum_show);
	$('#btn-cc-time-show').click(cc_time_show);

	cc_all_enrollment_plot();
//	cc_enrollment_plot();
//	cc_certified_plot();
//	cc_verified_plot();

	var cc_table = $('#cc_data').DataTable({
            dom: 'T<"clear">lfrtip',
	    "paging":   true,
	    "ordering": true,
	    "info":     true,
	    "searching":    true,
            "order": [ 1, 'desc' ],
	    "data": data['table'],
            // scrollY:        "300px",
            scrollY:        false,
            scrollX:        true,
            scrollCollapse: true,
            // paging:         false
	    // "columns" : data['tablecolumns'],
	    'columns': [{"title": "course_id", "class": "dt-center", "data": "course_id"}, 
			{"title": "registered_sum", "class": "dt-center", "data": "registered_sum"}, 
			{"title": "viewed_sum", "class": "dt-center", "data": "viewed_sum"}, 
			{"title": "explored_sum", "class": "dt-center", "data": "explored_sum"},
			{"title": "certified_sum", "class": "dt-center", "data": "certified_sum"},
			{"title": "n_male", "class": "dt-center", "data": "n_male"},
			{"title": "n_female", "class": "dt-center", "data": "n_female"},
			{"title": "n_verified_id", "class": "dt-center", "data": "n_verified_id"},
			{"title": "verified_viewed", "class": "dt-center", "data": "verified_viewed"},
			{"title": "verified_explored", "class": "dt-center", "data": "verified_explored"},
			{"title": "verified_certified", "class": "dt-center", "data": "verified_certified"},
			{"title": "verified_avg_grade", "class": "dt-center", "data": "verified_avg_grade"},
			{"title": "verified_n_male", "class": "dt-center", "data": "verified_n_male"},
			{"title": "verified_n_female", "class": "dt-center", "data": "verified_n_female"},
		       ],
        });
	new $.fn.dataTable.FixedColumns( cc_table );

    });
};


$(document).ready(function() {
    // cc_get_data();
});

