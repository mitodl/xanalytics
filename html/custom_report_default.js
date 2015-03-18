parameters = {{parameters}};
parameters.get_table_columns = true;

var make_report = function() {

  var nplots = 0; 
  var data = {};

  var report_div = $('#contain-{{report_name}}');
  
  // make data table
  var make_table = function(div_id, tablecolumns, tabledata){
    html = '<table id="' + div_id + '" class="display" width="100%"></table>';
    report_div.append(html);
    console.log('tablecolumns=', tablecolumns, ', tabledata=', tabledata);
    var table = $('#' + div_id).DataTable({
      // dom: 'T<"clear">lfrtip',
      "columns": tablecolumns,
      "pageLength": 10,
      searching: true,
      ordering: true,
      data: tabledata,
    });
  }

  var process_data = function(ajax_data){
    data['data'] = ajax_data['data'];
    html = '';
    // console.log("Processing data ", data);
    if (data.error){
      html = "Error!  " + data.error;
      console.log('error = ', data.error);
    }
    report_div.html(html);
    if (data.error){ return; }

      make_table('table-data-{{report_name}}', ajax_data['tablecolumns'], ajax_data['data']);
  }


  var add_new_plot = function(optarg){
    optarg = optarg || {};

    nplots += 1;
    var div_id = "plot" + String(nplots) + "-{{report_name}}";
    var html = '<div id="' + div_id + '" style="height: ' + (optarg.height || 400) + 'px"></div>'
    report_div.append(html);
    return div_id;
  }

  var make_scatter_plot = function(plot_title, series, optarg){

    optarg = optarg || {};
    var div_id = add_new_plot(optarg);

    console.log("series = ", series);

    // plot data
    var chart = new Highcharts.Chart({
      chart: { type: 'scatter',  zoomType: 'xy', renderTo: div_id },
      credits: {  enabled: false  },
      title : { text : plot_title,},
      xAxis: { title: { text: optarg.xtitle } },
      yAxis: { title: { text: optarg.ytitle},  min: optarg.ymin },
      plotOptions: {
        scatter: {
          marker: { radius: 10 },
          tooltip: {
            headerFormat: '<b>{series.name}</b><br>',
            pointFormat: optarg.pointFormat || '{point.name}',
          }
        }
      },
      series : series,
    });
    return chart;
  }

  var make_bar_plot = function(plot_title, xcategories, series, optarg){

    optarg = optarg || {};
    var div_id = add_new_plot(optarg);

    $('#'+div_id).highcharts({
      chart: {     type: 'column', zoomType: 'x' },
      credits: {  enabled: false  },
      title : {   text : plot_title },
      xAxis: {        categories: xcategories  },
      series : series,
    });
  }

  // make_bar_plot('test hist', ['a','b','c'], [{name:'test', data:[1,2,3]}]);


  var make_series = function(xcol, ycol, optarg){
    optarg = optarg || {};
    var sdat = [];
    var series = [ {name: optarg.name || "Data", data: sdat} ];
    data['data'].forEach(function(x){
      if (x[xcol]==null){ return; }
      if (x[xcol]==null){ return; }
      xv = Number(x[xcol]);
      yv = Number(x[ycol]);
      sdat.push({x: xv, y: yv, name: x[optarg.namecol || 'course_id']});
    });

    if (optarg.fit_line){
      series[0]['regression'] = true;
      series[0]['regressionSettings'] = { type: 'linear',
                                         // states: { hover: { lineWidth: 0 } },
                                         enableMouseTracking: false,
                                        }
    }

    return series;
  }   

  return {process_data: process_data,
          self: this,
          data: data,
         }

}

analytics_report = make_report();  // instantiate

if (1){
  $.getJSON(
    '/custom/get_report_data/{{report_name}}', 
    parameters,
    analytics_report.process_data
  );
}

