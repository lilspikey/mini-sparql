from sparql import parse_query
import unittest

class TestParsing(unittest.TestCase):

    def setUp(self):
        self.seq = range(10)

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
        

if __name__ == '__main__':
    unittest.main()