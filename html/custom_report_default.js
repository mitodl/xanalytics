parameters = {% autoescape off %}{{parameters}};{% endautoescape %}  // jshint ignore:line
parameters.get_table_columns = true;

var make_report = function() {

  var ntables = 0;
  var nplots = 0; 
  var data = {};

  var report_name = "{{report_name}}";
  var report_div = $('#contain-{{report_name}}');

  var add_text = function(text){  report_div.append("<p>"+text+"</p>");  }
  var new_section = function(title){ report_div.append("<br/><hr width='40%'/><h4>"+title+"</h4>"); }
  
  // jshint ignore:start 
  {% autoescape off %} {{cr_js_library["tables"]}} {% endautoescape %}
  {% autoescape off %} {{cr_js_library["plotting"]}} {% endautoescape %}
  // jshint ignore:end

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

