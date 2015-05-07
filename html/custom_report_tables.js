  // make data table
  var make_table = function(tablecolumns, tabledata, optarg){
    optarg = optarg || {};
    ntables += 1;
    var div_id = "table-" + report_name + "-" + ntables;
    var html = '<table id="' + div_id + '" class="display" width="' + (optarg.width || '100%') + '"></table>';
    report_div.append(html);
    // console.log('tablecolumns=', tablecolumns, ', tabledata=', tabledata);
    var table = $('#' + div_id).DataTable({
      dom: optarg.dom==null ? 'T<"clear">lfrtip' : optarg.dom,
      "columns": tablecolumns,
      "pageLength": 10,
      searching: optarg.searching==null ? true : optarg.searching,
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

  function numberWithCommas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }
