'use strict';

function schemaType(schema, depth=0) {
  if (!schema || depth > 6) return 'Unknown';
  if (schema.$ref) return schema.$ref.split('/').pop().replaceAll('~1','/').replaceAll('~0','~');
  if (schema.anyOf || schema.oneOf) return (schema.anyOf || schema.oneOf).map(item=>schemaType(item,depth+1)).join(' or ');
  if (schema.type === 'array') return 'array of '+schemaType(schema.items,depth+1);
  if (schema.type) return Array.isArray(schema.type)?schema.type.join(' or '):schema.type;
  if (schema.enum) return 'enum';
  if (schema.properties) return 'object';
  return 'Unknown';
}

function schemaConstraints(schema) {
  const labels = {minimum:'Minimum',maximum:'Maximum',exclusiveMinimum:'Greater than',exclusiveMaximum:'Less than',minLength:'Min length',maxLength:'Max length',pattern:'Pattern',minItems:'Min items',maxItems:'Max items',format:'Format',enum:'Allowed values'};
  return Object.entries(labels).filter(([key])=>Object.hasOwn(schema,key)).map(([key,label])=>label+': '+(typeof schema[key]==='string'?schema[key]:JSON.stringify(schema[key]))).join(' · ') || 'None declared';
}

function resolvedSchema(schema, schemas, seen=new Set()) {
  const prefix = '#/components/schemas/';
  if (!schema?.$ref?.startsWith(prefix)) return schema || {};
  const name = schema.$ref.slice(prefix.length).replaceAll('~1','/').replaceAll('~0','~');
  if (seen.has(name) || !Object.hasOwn(schemas,name)) return schema;
  return resolvedSchema(schemas[name],schemas,new Set([...seen,name]));
}

function schemaCard(label, schema, schemas) {
  const root=resolvedSchema(schema,schemas);
  const fields=root.type==='array'?resolvedSchema(root.items,schemas):root;
  const properties=Object.entries(fields.properties || {});
  const required=new Set(fields.required || []);
  const table=properties.length?`<div class="table-scroll"><table><thead><tr><th>FIELD</th><th>TYPE</th><th>REQUIRED</th><th>DEFAULT</th><th>CONSTRAINTS</th></tr></thead><tbody>${properties.map(([name,field])=>`<tr><td><code>${h(name)}</code>${field.description?`<p class="field-description">${h(field.description)}</p>`:''}</td><td><code>${h(schemaType(field))}</code></td><td>${required.has(name)?'Yes':'No'}</td><td><code>${h(Object.hasOwn(field,'default')?JSON.stringify(field.default):'None declared')}</code></td><td>${h(schemaConstraints(field))}</td></tr>`).join('')}</tbody></table></div>`:`<p class="detail-note">${h(schemaConstraints(root))}</p>`;
  return `<section class="schema-card"><div class="schema-title"><h3>${h(label)}</h3>${tag(schemaType(schema),'outline')}</div>${root.type==='array'?'<p class="detail-note">Fields of each array item:</p>':''}${table}<details class="schema-json"><summary>View declared JSON schema</summary>${code(JSON.stringify(root,null,2))}</details></section>`;
}

function schemaDetails(endpoint, schemas) {
  const cards=[];
  for (const parameter of endpoint.parameters) {
    if (['body','form','file'].includes(parameter.in) && Object.keys(parameter.schema || {}).length) cards.push(schemaCard('Request body · '+parameter.name,parameter.schema,schemas));
  }
  for (const response of endpoint.responses) {
    if (Object.keys(response.schema || {}).length) cards.push(schemaCard('Response '+response.status,response.schema,schemas));
  }
  return cards.length?'<div class="section-label">REQUEST AND RESPONSE FIELDS</div>'+cards.join(''):'';
}
