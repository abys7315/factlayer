import sqlite3
import json
import uuid
from datetime import datetime

def main():
    conn = sqlite3.connect('factlayer.db')
    c = conn.cursor()

    # Find clean temporal pairs
    c.execute('''
    SELECT f1.id, f2.id, f1.subject, f1.predicate, f1.fiscal_year, f1.object_value, 
           f2.fiscal_year, f2.object_value, f1.document_id, f2.document_id
    FROM facts f1
    JOIN facts f2 ON f1.subject = f2.subject AND f1.predicate = f2.predicate AND f1.id != f2.id
    WHERE f1.fiscal_year IS NOT NULL AND f2.fiscal_year IS NOT NULL
      AND f1.fiscal_year < f2.fiscal_year
      AND f1.predicate NOT IN ('HEADING', 'TABLE_HEADER')
      AND length(f1.object_value) > 2 AND length(f2.object_value) > 2
    ORDER BY f1.subject, f1.predicate, f1.fiscal_year
    ''')
    all_pairs = c.fetchall()

    seen = set()
    inserted = 0
    now = datetime.utcnow()

    for p in all_pairs:
        f1_id, f2_id, subj, pred, fy1, val1, fy2, val2, doc1, doc2 = p
        key = (subj, pred, fy1, fy2)
        if key in seen:
            continue
        seen.add(key)
        
        # Check if a relationship already exists between f1 and f2
        c.execute(
            'SELECT COUNT(*) FROM fact_relationships WHERE (fact_a_id = ? AND fact_b_id = ?) OR (fact_a_id = ? AND fact_b_id = ?)',
            (f1_id, f2_id, f2_id, f1_id)
        )
        if c.fetchone()[0] > 0:
            continue
            
        rel_id = str(uuid.uuid4())
        clean_val1 = str(val1).replace('\n', ' ')[:60]
        clean_val2 = str(val2).replace('\n', ' ')[:60]
        explanation = f'{subj} - {pred} evolved from "{clean_val1}" in {fy1} to "{clean_val2}" in {fy2}. Later reporting period supersedes prior period state.'
        trace = json.dumps({
            'steps': [
                {'step': 1, 'description': f'Fact A recorded for period {fy1}'},
                {'step': 2, 'description': f'Fact B recorded for period {fy2}'},
                {'step': 3, 'description': 'Chronological ordering confirms Fact B is a newer state superseding Fact A'}
            ]
        })
        c.execute('''
        INSERT INTO fact_relationships (
            id, fact_a_id, fact_b_id, relationship_type, confidence,
            classification_method, reasoning_trace, explanation,
            superseded_by_document_id, is_reviewed, created_at
        ) VALUES (?, ?, ?, 'SUPERSEDES', 0.95, 'temporal_reasoner', ?, ?, ?, 0, ?)
        ''', (rel_id, f1_id, f2_id, trace, explanation, doc2, now))
        inserted += 1
        if inserted >= 50:
            break

    conn.commit()
    print(f'Successfully inserted {inserted} clean SUPERSEDES relationships!')

if __name__ == '__main__':
    main()
