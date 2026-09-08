import urllib.request
import json

def test(url, name):
    try:
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode())
        nodes = len(data.get('nodes', []))
        edges = len(data.get('edges', []))
        scope = data.get('filter_scope')
        total_rels = data.get('stats', {}).get('total_relationships')
        print(f"{name}: {nodes} nodes, {edges} edges, scope={scope}, total_rels={total_rels}")
    except Exception as e:
        print(f"{name} FAILED: {e}")

if __name__ == '__main__':
    test('http://127.0.0.1:8000/api/v1/graph', 'Default')
    test('http://127.0.0.1:8000/api/v1/graph?preset=contradictions', 'Contradictions')
    test('http://127.0.0.1:8000/api/v1/graph?preset=supersedes', 'Supersedes')
    test('http://127.0.0.1:8000/api/v1/graph?preset=corroborations', 'Corroborations')
    test('http://127.0.0.1:8000/api/v1/graph?preset=contextual', 'Contextual')
    
    import sqlite3
    conn = sqlite3.connect('factlayer.db')
    c = conn.cursor()
    c.execute('SELECT id FROM documents LIMIT 1')
    doc_id = c.fetchone()[0]
    test(f'http://127.0.0.1:8000/api/v1/graph?document_id={doc_id}', f'Document ({doc_id[:8]})')

    c.execute('SELECT id FROM fact_relationships LIMIT 1')
    rel_id = c.fetchone()[0]
    test(f'http://127.0.0.1:8000/api/v1/graph?relationship_id={rel_id}', f'Relationship ({rel_id[:8]})')
