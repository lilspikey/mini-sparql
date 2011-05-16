from sparql import parse_query, add_triples, match_triples, query, clear_triples
import unittest

class TestParsing(unittest.TestCase):

    def test_parse_query_select(self):
        p = parse_query("""SELECT ?title
        WHERE
        {
          <http://example.org/book/book1> <http://purl.org/dc/elements/1.1/title> ?title .
        }""")
        
        self.assertTrue(hasattr(p, 'query'))
        name, variables, triples = p.query
        self.assertEqual('SELECT', name)
        self.assertEqual(1, len(variables))
        self.assertEquals('?title', variables[0])
        self.assertEquals(1, len(triples))
        triple = triples[0]
        self.assertEqual(3, len(triple))
        self.assertEqual('<http://example.org/book/book1>', triple[0])
        self.assertEqual('<http://purl.org/dc/elements/1.1/title>', triple[1])
        self.assertEqual('?title', triple[2])
    
    def test_parse_query_select_with_prefix(self):
        p = parse_query("""PREFIX foaf:   <http://xmlns.com/foaf/0.1/>
        SELECT ?x ?name
        WHERE  { ?x foaf:name ?name }""")
        
        self.assertTrue(hasattr(p, 'prologue'))
        self.assertTrue(hasattr(p.prologue, 'prefixes'))
        prefixes = p.prologue.prefixes
        self.assertEqual(1, len(prefixes))
        prefix = prefixes[0]
        self.assertTrue(hasattr(prefix, 'name'))
        self.assertEqual('foaf:', prefix.name)
        self.assertTrue(hasattr(prefix, 'value'))
        self.assertEqual('<http://xmlns.com/foaf/0.1/>', prefix.value)
        
        name, variables, triples = p.query
        self.assertEqual(2, len(variables))
        self.assertEqual('?x', variables[0])
        self.assertEqual('?name', variables[1])
        
        self.assertEqual(1, len(triples))
        triple = triples[0]
        self.assertEqual('?x', triple[0])
        self.assertEqual('foaf:name', triple[1])
        self.assertEqual('?name', triple[2])

class TestMatchTriples(unittest.TestCase):
    
    def setUp(self):
        clear_triples()
    
    def test_match_triples(self):
        add_triples(('a', 'name', 'c'), ('b', 'name', 'd'), ('a', 'weight', 'c'))
        
        self.assertEqual([{}], list(match_triples(('a', 'name', 'c'))))
        self.assertEqual([dict(value='c')],
                         list(match_triples(('a', 'name', '?value'))))
        self.assertEqual([dict(id='a', value='c'),
                          dict(id='b', value='d')],
                         list(match_triples(('?id', 'name', '?value'))))
        self.assertEqual([dict(id='a', property='name', value='c'),
                          dict(id='b', property='name', value='d'),
                          dict(id='a', property='weight', value='c')],
                         list(match_triples(('?id', '?property', '?value'))))

class TestQuery(unittest.TestCase):
    
    def setUp(self):
        clear_triples()
        add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'))
    
    def test_query_simple(self):
        self.assertEqual(
            [('a', 'name-a'), ('b', 'name-b')],
            list(query('SELECT ?id ?name WHERE { ?id name ?name }'))
        )
    
    def test_query_join(self):
        self.assertEqual(
            [('a', 'name-a', 'weight-a')],
            list(query('SELECT ?id ?name ?weight WHERE { ?id name ?name . ?id weight ?weight }'))
        )
    
    def test_query_join_unmatchable(self):
        self.assertEqual(
            [],
            list(query('SELECT ?id ?weight WHERE { ?id name ?name . ?name weight ?weight }'))
        )
    
    def test_query_union(self):
        self.assertEqual(
            [('a', 'name-a', None), ('b', 'name-b', None), ('a', None, 'weight-a')],
            list(query('SELECT ?id ?name ?weight WHERE { { ?id name ?name} UNION {?id weight ?weight} }'))
        )
    
    def test_single_optional(self):
        self.assertEqual(
            [('a', 'name-a', 'weight-a'), ('b', 'name-b', None)],
            list(query('SELECT ?id ?value ?weight WHERE { ?id name ?value OPTIONAL {?id weight ?weight} }'))
        )
    
    def test_multiple_optional(self):
        self.assertEqual(
            [('a', 'name-a', 'weight-a', None), ('b', 'name-b', None, 'size-b')],
            list(query('''SELECT ?id ?value ?weight ?size
                        WHERE { ?id name ?value 
                        OPTIONAL {?id weight ?weight}
                        OPTIONAL {?id size ?size} }'''))
        )


if __name__ == '__main__':
    unittest.main()