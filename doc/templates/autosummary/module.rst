{{ fullname }}
{{ underline }}

.. automodule:: {{ fullname }}

   {% block functions %}
   {% if functions or methods %}
   .. rubric:: Functions

   {% for item in functions %}
   .. autofunction:: {{ item }}
   {%- endfor %}

   {% for item in methods %}
   .. automethod:: {{ item }}
   {%- endfor %}

   {% endif %}
   {% endblock %}


   {% block classes %}
   {% if classes %}
   .. rubric:: Classes

   .. autosummary::
      :toctree:
   {% for item in classes %}
      {{ item }}
   {%- endfor %}

   {% endif %}
   {% endblock %}


   {% block exceptions %}
   {% if exceptions %}
   .. rubric:: Exceptions

   .. autosummary::
      :toctree:
   {% for item in classes %}
      {{ item }}
   {%- endfor %}

   {% endif %}
   {% endblock %}


   {% block members %}
   {% set datamembers = [] %}

   {% for item in members %}
   {% if "__" not in item and item.isupper() %}
      {% set dummy = datamembers.append(item) %}
   {% endif %}
   {% endfor %}

   {% if datamembers|length > 0 %}
   .. rubric:: Constant Members
   {% for item in datamembers %}
   .. autodata:: {{ item }}
      :annotation:
   {%- endfor %}
   {% endif %}

   {% endblock %}
