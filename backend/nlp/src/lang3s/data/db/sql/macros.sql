{% macro match_paths(column, input_list) %}
    {% if input_list and input_list|length > 0 %}
        (
        {% for item in input_list %}
            ({{ column }} = ? OR {{ column }} LIKE ?)
            {% if not loop.last %} OR {% endif %}
        {% endfor %}
        )
    {% else %}
        -- Fallback for empty list:
        -- Use 1=1 if you want to return ALL data when no filter is provided
        -- Use 1=0 if you want to return NO data when no filter is provided
        1=1
    {% endif %}
{% endmacro %}