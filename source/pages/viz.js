'use strict';

const get = id => document.getElementById(id);
const bundle = JSON.parse(get('bundle-data').textContent);
const documents = new Map(bundle.documents.map(doc => [doc.path, doc]));
const relationships = new Map(bundle.relationships.map(edge => [edge.key, edge]));
const firstDocument = {
  case: bundle.nodes[bundle.relationships[0].source],
  archive: 'site-bundle/index.md',
  walkthroughs: 'evaluation/BEGINNER-WALKTHROUGH.md'
};
let view;
let selection;

const docHref = path => '#document/' + encodeURIComponent(path);
const edgeHref = key => '#relationship/' + encodeURIComponent(key);

function link(label, href, className = '') {
  const a = document.createElement('a');
  a.textContent = label;
  a.href = href;
  a.className = className;
  return a;
}

function conceptLink(id) {
  const doc = documents.get(bundle.nodes[id]);
  return link(doc.title, docHref(doc.path), 'graph-node');
}

function edgeLink(edge) {
  const a = link(edge.label, edgeHref(edge.key), 'graph-relation');
  a.setAttribute('aria-label', edge.label);
  return a;
}

function renderGraph() {
  const [first, ...controls] = bundle.relationships;
  const children = document.createElement('div');
  children.className = 'graph-children';
  for (const edge of controls) {
    const branch = document.createElement('div');
    branch.className = 'graph-branch';
    branch.append(edgeLink(edge), conceptLink(edge.target));
    children.append(branch);
  }
  get('graph').append(conceptLink(first.source), edgeLink(first), conceptLink(first.target), children);
}

function listItem(element) {
  const li = document.createElement('li');
  li.append(element);
  return li;
}

function markCurrent(container, href) {
  for (const a of get(container).querySelectorAll('a')) {
    if (a.getAttribute('href') === href) a.setAttribute('aria-current', 'true');
    else a.removeAttribute('aria-current');
  }
}

function viewDocuments() {
  return bundle.documents.filter(doc => doc.view === view);
}

function renderResults() {
  const words = get('query').value.trim().toLocaleLowerCase('en-GB').split(/\s+/).filter(Boolean);
  const kind = get('kind').value;
  const matches = viewDocuments().filter(doc =>
    (!kind || doc.kind === kind) && words.every(word => doc.search.includes(word))
  );
  get('results').replaceChildren(...matches.map(doc => listItem(link(doc.title, docHref(doc.path)))));
  get('result-count').textContent = matches.length === 1 ? '1 document' : matches.length + ' documents';
  markCurrent('results', selection);
}

function updateView(next) {
  if (next === view) return;
  view = next;
  get('query').value = '';
  get('kind').replaceChildren(new Option('All types', ''));
  const kinds = [...new Set(viewDocuments().map(doc => doc.kind))].sort();
  for (const kind of kinds) get('kind').add(new Option(kind, kind));
  get('graph-card').hidden = view !== 'case';
  markCurrent('views', '#' + view);
}

function writeMetadata(id, fields) {
  const element = get(id);
  element.replaceChildren();
  for (const [term, value] of fields) {
    if (!value) continue;
    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.textContent = term;
    if (typeof value === 'string') dd.textContent = value;
    else dd.append(value);
    element.append(dt, dd);
  }
}

function renderDocument(doc, focus) {
  updateView(doc.view);
  selection = docHref(doc.path);
  get('relationship').hidden = true;
  get('record').hidden = false;
  get('record-title').textContent = doc.title;
  get('record-kind').textContent = doc.kind;
  get('record-summary').textContent = doc.summary;
  writeMetadata('record-meta', [
    ['Status', doc.status], ['Verification', doc.verification], ['Generated', doc.generated],
    ['Stale after', doc.reviewBy], ['Publisher', doc.source && link('Open source', doc.source)]
  ]);
  // The body was rendered from the captured, public Markdown with raw HTML disabled.
  get('record-body').innerHTML = doc.body;
  for (const image of get('record-body').querySelectorAll('img[data-embedded]')) {
    image.src = bundle.images[image.dataset.embedded];
  }
  const related = bundle.relationships.flatMap(edge => {
    if (bundle.nodes[edge.source] === doc.path) {
      return [listItem(link(edge.label + ' → ' + documents.get(bundle.nodes[edge.target]).title, edgeHref(edge.key)))];
    }
    if (bundle.nodes[edge.target] === doc.path) {
      return [listItem(link(documents.get(bundle.nodes[edge.source]).title + ' → ' + edge.label, edgeHref(edge.key)))];
    }
    return [];
  });
  get('links-list').replaceChildren(...related);
  get('record-links').hidden = related.length === 0;
  if (focus) get('record-title').focus();
}

function renderRelationship(edge, focus) {
  updateView('case');
  selection = edgeHref(edge.key);
  get('record').hidden = true;
  get('relationship').hidden = false;
  const from = documents.get(bundle.nodes[edge.source]);
  const to = documents.get(bundle.nodes[edge.target]);
  const witness = edge.evidence[0];
  get('relationship-title').textContent = edge.label;
  get('direction').replaceChildren(link(from.title, docHref(from.path)), ' → ', link(to.title, docHref(to.path)));
  get('back-to-concept').href = docHref(from.path);
  writeMetadata('relationship-meta', [
    ['Scope', edge.assertion_scope], ['Authority', edge.authority.label],
    ['Source locator', witness.locator], ['SHA-256', witness.source_value_sha256]
  ]);
  get('passage').textContent = witness.source_value;
  get('publisher').href = witness.url;
  get('pinned').href = witness.resource;
  if (focus) get('relationship-title').focus();
}

function readRoute(focus) {
  let route = '';
  try {
    route = decodeURIComponent(location.hash.slice(1));
  } catch (error) {
    if (!(error instanceof URIError)) throw error;
  }
  if (route === 'reader' && view) return;
  const doc = route.startsWith('document/') && documents.get(route.slice(9));
  const edge = route.startsWith('relationship/') && relationships.get(route.slice(13));
  if (edge) renderRelationship(edge, focus);
  else {
    const landing = Object.hasOwn(firstDocument, route) ? firstDocument[route] : firstDocument.case;
    renderDocument(doc || documents.get(landing), focus && Boolean(doc));
  }
  markCurrent('graph', selection);
  renderResults();
}

get('query').addEventListener('input', renderResults);
get('kind').addEventListener('change', renderResults);
get('reset').addEventListener('click', () => {
  get('query').value = '';
  get('kind').value = '';
  renderResults();
  get('query').focus();
});
window.addEventListener('hashchange', () => readRoute(true));
renderGraph();
readRoute(false);
