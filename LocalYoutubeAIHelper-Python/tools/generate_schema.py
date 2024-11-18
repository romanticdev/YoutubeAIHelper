import json
from genson import SchemaBuilder

# Sample JSON object
json_data = {
    "summary": "asdasd"
}

# Initialize the schema builder
builder = SchemaBuilder()
builder.add_object(json_data)

# Build the schema
schema = builder.to_schema()

# Set "additionalProperties" to false
if schema.get('type') == 'object':
    schema['additionalProperties'] = False

# Output the schema
print(json.dumps(schema, indent=4))
