parameters = {% autoescape off %}{{parameters}};{% endautoescape %}  // jshint ignore:line
parameters.get_table_columns = true;

var make_report = function() {

  var ntables = 0;
  var nplots = 0; 
  var data = {};

  var report_div = $('#contain-{{report_name}}');

  var add_text = function(text){
    report_div.append("<p>"+text+"</p>");
  }
  
  var new_section = function(title){
    report_div.append("<br/><hr width='40%'/><h4>"+title+"</h4>");
  }
  
  // make data table
  var make_table = function(tablecolumns, tabledata, optarg){
    optarg = optarg || {};
    ntables += 1;
    var div_id = "table-{{report_name}}-" + ntables;
    var html = '<table id="' + div_id + '" class="display" width="100%"></table>';
    report_div.append(html);
    // console.log('tablecolumns=', tablecolumns, ', tabledata=', tabledata);
    var table = $('#' + div_id).DataTable({
      dom: 'T<"clear">lfrtip',
      "columns": tablecolumns,
      "pageLength": 10,
      searching: true,
      search:{"regex": true},
      ordering: optarg.ordering==null ? true : optarg.ordering,
      paging: optarg.paging==null ? true : optarg.paging,
      order: optarg.order,
      data: tabledata,
      // formatNumber: function ( toFormat ) { 
      //   return toFormat.toString().replace( /\B(?=(\d{3})+(?!\d))/g, "," ); 
      // },
    });
  }

  // make table column entry
  var colent = function(title, cname, optarg){
    var retdat = {'data': cname, 'title': title, 'class': 'dt-center'};
    optarg = optarg || {};
    if (optarg.commas){
      retdat['render'] = numberWithCommas;
    }
    var render_scaled = function(scale, digits){
      return function(x){
        if (typeof x == "number"){
          return numberWithCommas((x * scale).toFixed(digits));
        }else{
          return x;
        }
      }
    }
    if (optarg.thousands){
      retdat['render'] = render_scaled(1/1000, 2);
    }
    if (optarg.mkpct){
      retdat['render'] = render_scaled(100, 2);
    }
    if (optarg.fixed != null){
      retdat['render'] = render_scaled(1, optarg.fixed);
    }
    return retdat
  }

  // main function called to process data from AJAX call
  var process_data = function(ajax_data){
    html = '';
    // console.log("Processing data ", ajax_data);
    if (ajax_data.error){
      html = "Error!  " + ajax_data.error;
      console.log('error = ', ajax_data.error);
    }
    report_div.html(html);
    data['data'] = ajax_data['data'];
    if (ajax_data.error){ return; }

      make_table(ajax_data['tablecolumns'], ajax_data['data']);
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

  function numberWithCommas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
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

