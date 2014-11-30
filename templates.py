import os
import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + "/html"),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
