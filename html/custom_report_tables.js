  // make data table
  var make_table = function(tablecolumns, tabledata, optarg){
    optarg = optarg || {};
    ntables += 1;
    var div_id = "table-" + (optarg.report_name || report_name) + "-" + ntables;
    var html = '<table id="' + div_id + '" class="display" width="' + (optarg.width || '100%') + '"></table>';
    (optarg.report_div || report_div).append(html);
    // console.log('tablecolumns=', tablecolumns, ', tabledata=', tabledata);
    var table = $('#' + div_id).DataTable({
      dom: optarg.dom==null ? 'T<"clear">lfrtip' : optarg.dom,
      "columns": tablecolumns,
      "pageLength": optarg.pageLength || 10,
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
    return div_id;
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
    var render_simple_date = function(nchars){
      return function(x){
	try{
          return x.toISOString().substring(0, nchars);
	}
	catch(err){
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
    if (optarg.simpledate != null){
      retdat['render'] = render_simple_date(optarg.simpledate);
    }
    return retdat
  }

  function numberWithCommas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  // put a div within a show / hide enclosure, with toggle button
  function make_show_hide(title, div_id){
      var div_elem = $('#' + div_id);
      var html = "<button style='float:right' id='" + div_id + "_showhide'></button>";
      div_elem.before(html);
      var sh_elem = $('#' + div_id + "_showhide");
      var hide = function(){
	  div_elem.hide();
	  sh_elem.html("Show " + title);
	  sh_elem.data('state', 'hidden');
      }
      var show = function(){
	  div_elem.show();
	  sh_elem.html("Hide " + title);
	  sh_elem.data('state', 'visible');
      }
      var toggle = function(){
	  var state = sh_elem.data().state;
	  if (state=='hidden'){
	      show();
	  }else{
	      hide();
	  }
      }
      sh_elem.click(toggle);
      hide();
  }
