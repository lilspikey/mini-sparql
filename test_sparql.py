from sparql import parse_query, add_triples, match_triples, query, \
                   clear_triples, Pattern, PatternGroup, OptionalGroup, \
                   UnionGroup
import unittest

class TestParsing(unittest.TestCase):

    def test_parse_query_select(self):
        p = parse_query("""SELECT ?title
        WHERE
        {
          <http://example.org/book/book1> <http://purl.org/dc/elements/1.1/title> ?title .
        }""")
        
        self.assertTrue(hasattr(p, 'query'))
        name, variables, pattern = p.query

        self.assertEqual('SELECT', name)
        self.assertEqual(1, len(variables))
        self.assertEquals('?title', variables[0])
        self.assertTrue(isinstance(pattern, Pattern))
        triple = pattern.pattern
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
        
        name, variables, pattern = p.query
        self.assertEqual(2, len(variables))
        self.assertEqual('?x', variables[0])
        self.assertEqual('?name', variables[1])
        
        self.assertTrue(isinstance(pattern, Pattern))
        triple = pattern.pattern
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

class TestPattern(unittest.TestCase):
    
    def setUp(self):
        clear_triples()
        add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'))
        self.p = Pattern('?id', 'name', '?name')
    
    def test_match_empty_solution(self):
        self.assertEqual(
            [dict(id='a', name='name-a'), dict(id='b', name='name-b')],
            list(self.p.match({}))
        )

    def test_match_with_constraining_solution(self):
        self.assertEqual(
            [dict(id='a', name='name-a')],
            list(self.p.match({'id': 'a'}))
        )
        self.assertEqual(
            [dict(id='b', name='name-b')],
            list(self.p.match({'name': 'name-b'}))
        )
    
    def test_match_with_nonconstraining_solution(self):
        self.assertEqual(
            [dict(id='a', name='name-a', bar='two'),
             dict(id='b', name='name-b', bar='two')],
            list(self.p.match({'bar': 'two'}))
        )

class TestOptionalGroup(unittest.TestCase):
    
    def setUp(self):
        clear_triples()
        add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'))
        self.p = OptionalGroup(Pattern('?id', 'name', '?name'))
    
    def test_match_empty_solution(self):
        self.assertEqual(
            [dict(id='a', name='name-a'), dict(id='b', name='name-b')],
            list(self.p.match({}))
        )
    
    def test_match_with_constraining_solution(self):
        self.assertEqual(
            [dict(id='a', name='name-a')],
            list(self.p.match({'id': 'a'}))
        )
        self.assertEqual(
            [dict(id='b', name='name-b')],
            list(self.p.match({'name': 'name-b'}))
        )
        self.assertEqual(
            [dict(id='c')],
            list(self.p.match({'id': 'c'}))
        )
        self.assertEqual(
            [dict(id='c', name='name-c')],
            list(self.p.match({'id': 'c', 'name': 'name-c'}))
        )
    
    def test_match_with_nonconstraining_solution(self):
        self.assertEqual(
            [dict(id='a', name='name-a', bar='two'),
             dict(id='b', name='name-b', bar='two')],
            list(self.p.match({'bar': 'two'}))
        )

class TestUnionGroup(unittest.TestCase):

    def setUp(self):
        clear_triples()
        add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'))
        self.p = UnionGroup(Pattern('?id', 'name', '?name'),
                            Pattern('?id', 'weight', '?weight'))

    def test_match_empty_solution(self):
        self.assertEqual(
            [dict(id='a', name='name-a'), dict(id='b', name='name-b'),
             dict(id='a', weight='weight-a')],
            list(self.p.match({}))
        )
    
    def test_match_with_constraining_solution(self):
        self.assertEqual(
            [dict(id='a', name='name-a'), dict(id='a', weight='weight-a')],
            list(self.p.match({'id': 'a'}))
        )
        self.assertEqual(
            [dict(id='b', name='name-b'), dict(id='a', weight='weight-a', name='name-b')],
            list(self.p.match({'name': 'name-b'}))
        )
        self.assertEqual(
            [],
            list(self.p.match({'id': 'c'}))
        )

class TestPatternGroup(unittest.TestCase):

    def setUp(self):
        clear_triples()
        add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'))
    
    def test_match_empty_solution(self):
        p = PatternGroup([Pattern('?id', 'name', '?name'),
                          Pattern('?id', 'weight', '?weight')])
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a')],
            list(p.match({}))
        )
    
    def test_match_with_constraining_solution(self):
        p = PatternGroup([Pattern('?id', 'name', '?name'),
                          Pattern('?id', 'weight', '?weight')])
        self.assertEqual(
            [],
            list(p.match({'id': 'b'}))
        )
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a')],
            list(p.match({'id': 'a'}))
        )
    
    def test_with_optional(self):
        p = PatternGroup([Pattern('?id', 'name', '?name'),
                          OptionalGroup(Pattern('?id', 'weight', '?weight'))])
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a'),
             dict(id='b', name='name-b')],
            list(p.match({}))
        )
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a')],
            list(p.match({'id': 'a'}))
        )
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-b')],
            list(p.match({'id': 'a', 'weight': 'weight-b'}))
        )

    def test_with_optional_multiple(self):
        p = PatternGroup([Pattern('?id', 'name', '?name'),
                          OptionalGroup(Pattern('?id', 'weight', '?weight')),
                          OptionalGroup(Pattern('?id', 'size', '?size'))])
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a'),
             dict(id='b', name='name-b', size='size-b')],
            list(p.match({}))
        )
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a')],
            list(p.match({'id': 'a'}))
        )
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-b')],
            list(p.match({'id': 'a', 'weight': 'weight-b'}))
        )
        self.assertEqual(
            [dict(id='b', name='name-b', size='size-b')],
            list(p.match({'id': 'b'}))
        )

    def test_with_optional_group(self):
        p = PatternGroup([Pattern('?id', 'name', '?name'),
                          OptionalGroup(
                            PatternGroup([Pattern('?id', 'weight', '?weight'),
                                          Pattern('?id', 'size', '?size')])
                          )])
        self.assertEqual(
            [dict(id='a', name='name-a'),
             dict(id='b', name='name-b')],
            list(p.match({}))
        )
        
        add_triples(('a', 'size', 'size-a'))
        
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a', size='size-a'),
             dict(id='b', name='name-b')],
            list(p.match({}))
        )
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a', size='size-a')],
            list(p.match({'id': 'a'}))
        )
        self.assertEqual(
            [dict(id='b', name='name-b')],
            list(p.match({'id': 'b'}))
        )


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