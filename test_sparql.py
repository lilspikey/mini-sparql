from sparql import TripleStore, Pattern, PatternGroup, OptionalGroup, \
                   UnionGroup, Index, VariableExpression, LiteralExpression
import unittest

class TestParsing(unittest.TestCase):
    
    def setUp(self):
        self.store = TripleStore()
    
    def test_parse_query_select(self):
        p = self.store.parse_query("""SELECT ?title
        WHERE
        {
          <http://example.org/book/book1> <http://purl.org/dc/elements/1.1/title> ?title .
        }""")
        
        self.assertTrue(hasattr(p, 'query'))
        _, variables, pattern = p.query
        
        self.assertEqual(1, len(variables))
        self.assertTrue(isinstance(variables[0], VariableExpression))
        self.assertEquals('title', variables[0].name)
        self.assertTrue(isinstance(pattern, Pattern))
        triple = pattern.pattern
        self.assertEqual(3, len(triple))
        self.assertEqual('http://example.org/book/book1', triple[0].value)
        self.assertEqual('http://purl.org/dc/elements/1.1/title', triple[1].value)
        self.assertEqual('title', triple[2].name)
    
    def test_parse_query_select_with_prefix(self):
        p = self.store.parse_query("""PREFIX foaf: <http://xmlns.com/foaf/0.1/>
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
        self.assertEqual('http://xmlns.com/foaf/0.1/', prefix.value)
        
        name, variables, pattern = p.query
        self.assertEqual(2, len(variables))
        self.assertTrue(isinstance(variables[0], VariableExpression))
        self.assertEquals('x', variables[0].name)
        self.assertTrue(isinstance(variables[1], VariableExpression))
        self.assertEquals('name', variables[1].name)
        
        self.assertTrue(isinstance(pattern, Pattern))
        triple = pattern.pattern
        self.assertTrue(isinstance(triple[0], VariableExpression))
        self.assertEquals('x', triple[0].name)
        self.assertEqual('http://xmlns.com/foaf/0.1/name', triple[1].value)
        self.assertTrue(isinstance(triple[2], VariableExpression))
        self.assertEqual('name', triple[2].name)


class TestExpressionParser(unittest.TestCase):
    
    def test__arithmetic_parser(self):
        from sparql import _arithmetic_parser
        p = _arithmetic_parser()
        toks = p.parseString('?a + ?b * 2')
        self.assertTrue(toks is not None)
        self.assertEqual(1, len(toks))
        e = toks[0]
        self.assertEqual(1, e.resolve(dict(a=1, b=0)))
        self.assertEqual(2, e.resolve(dict(a=2, b=0)))
        self.assertEqual(2, e.resolve(dict(a=0, b=1)))
        self.assertEqual(4, e.resolve(dict(a=0, b=2)))
        self.assertEqual(5, e.resolve(dict(a=1, b=2)))
        self.assertEqual(10, e.resolve(dict(a=2, b=4)))

    def test__comparison_parser(self):
        from sparql import _comparison_parser
        p = _comparison_parser()
        toks = p.parseString('?a < 10')
        self.assertTrue(toks is not None)
        self.assertEqual(1, len(toks))
        e = toks[0]
        self.assertTrue(e.resolve(dict(a=1)))
        self.assertTrue(e.resolve(dict(a=9)))
        self.assertFalse(e.resolve(dict(a=10)))

    def test__comparison_parser_with_arithmetic(self):
        from sparql import _comparison_parser
        p = _comparison_parser()
        toks = p.parseString('2 * ?a < 10')
        self.assertTrue(toks is not None)
        self.assertEqual(1, len(toks))
        e = toks[0]
        self.assertTrue(e.resolve(dict(a=1)))
        self.assertTrue(e.resolve(dict(a=4)))
        self.assertFalse(e.resolve(dict(a=5)))
        self.assertFalse(e.resolve(dict(a=9)))
        self.assertFalse(e.resolve(dict(a=10)))


class TestMatchTriples(unittest.TestCase):
    
    def setUp(self):
        self.store = TripleStore()
    
    def test_match_triples(self):
        self.store.add_triples(('a', 'name', 'c'),
                               ('b', 'name', 'd'),
                               ('a', 'weight', 'c'))
        
        self.assertEqual([{}],
            list(self.store.match_triples(
                    (
                        LiteralExpression('a'),
                        LiteralExpression('name'),
                        LiteralExpression('c')))
                    )
                )
        self.assertEqual([dict(value='c')],
                         list(self.store.match_triples(
                            (
                                LiteralExpression('a'),
                                LiteralExpression('name'),
                                VariableExpression('value')
                            )
                        )))
        self.assertEqual([dict(id='a', value='c'),
                          dict(id='b', value='d')],
                         list(self.store.match_triples(
                                (
                                    VariableExpression('id'),
                                    LiteralExpression('name'),
                                    VariableExpression('value')
                                )
                        )))
        self.assertEqual([dict(id='a', property='name', value='c'),
                          dict(id='b', property='name', value='d'),
                          dict(id='a', property='weight', value='c')],
                         list(self.store.match_triples(
                                    (
                                        VariableExpression('id'),
                                        VariableExpression('property'),
                                        VariableExpression('value')
                                    )
                            )))

class TestPattern(unittest.TestCase):
    
    def setUp(self):
        self.store = TripleStore()
        self.store.add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'))
        self.p = Pattern(self.store, VariableExpression('id'), LiteralExpression('name'), VariableExpression('name'))
    
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
        self.store = TripleStore()
        self.store.add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'))
        self.p = OptionalGroup(Pattern(self.store, VariableExpression('id'), LiteralExpression('name'), VariableExpression('name')))
    
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
        self.store = TripleStore()
        self.store.add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'))
        self.p = UnionGroup(Pattern(self.store, VariableExpression('id'), LiteralExpression('name'), VariableExpression('name')),
                            Pattern(self.store, VariableExpression('id'), LiteralExpression('weight'), VariableExpression('weight')))

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
        self.store = TripleStore()
        self.store.add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'))
    
    def test_match_empty_solution(self):
        p = PatternGroup([Pattern(self.store, VariableExpression('id'), LiteralExpression('name'), VariableExpression('name')),
                          Pattern(self.store, VariableExpression('id'), LiteralExpression('weight'), VariableExpression('weight'))])
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a')],
            list(p.match({}))
        )
    
    def test_match_with_constraining_solution(self):
        p = PatternGroup([Pattern(self.store, VariableExpression('id'), LiteralExpression('name'), VariableExpression('name')),
                          Pattern(self.store, VariableExpression('id'), LiteralExpression('weight'), VariableExpression('weight'))])
        self.assertEqual(
            [],
            list(p.match({'id': 'b'}))
        )
        self.assertEqual(
            [dict(id='a', name='name-a', weight='weight-a')],
            list(p.match({'id': 'a'}))
        )
    
    def test_with_optional(self):
        p = PatternGroup([Pattern(self.store, VariableExpression('id'), LiteralExpression('name'), VariableExpression('name')),
                          OptionalGroup(Pattern(self.store, VariableExpression('id'), LiteralExpression('weight'), VariableExpression('weight')))])
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
        p = PatternGroup([Pattern(self.store, VariableExpression('id'), LiteralExpression('name'), VariableExpression('name')),
                          OptionalGroup(Pattern(self.store, VariableExpression('id'), LiteralExpression('weight'), VariableExpression('weight'))),
                          OptionalGroup(Pattern(self.store, VariableExpression('id'), LiteralExpression('size'), VariableExpression('size')))])
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
        p = PatternGroup([Pattern(self.store, VariableExpression('id'), LiteralExpression('name'), VariableExpression('name')),
                          OptionalGroup(
                            PatternGroup([Pattern(self.store, VariableExpression('id'), LiteralExpression('weight'), VariableExpression('weight')),
                                          Pattern(self.store, VariableExpression('id'), LiteralExpression('size'), VariableExpression('size'))])
                          )])
        self.assertEqual(
            [dict(id='a', name='name-a'),
             dict(id='b', name='name-b')],
            list(p.match({}))
        )
        
        self.store.add_triples(('a', 'size', 'size-a'))
        
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
        self.store = TripleStore()
        self.store.add_triples(('a', 'name', 'name-a'), ('b', 'name', 'name-b'),
                    ('a', 'weight', 'weight-a'), ('b', 'size', 'size-b'),
                    ('a', 'height', 100))
    
    def test_query_simple(self):
        self.assertEqual(
            [('a', 'name-a'), ('b', 'name-b')],
            list(self.store.query('SELECT ?id ?name WHERE { ?id name ?name }'))
        )
    
    def test_query_join(self):
        self.assertEqual(
            [('a', 'name-a', 'weight-a')],
            list(self.store.query('SELECT ?id ?name ?weight WHERE { ?id name ?name . ?id weight ?weight }'))
        )
    
    def test_query_join_unmatchable(self):
        self.assertEqual(
            [],
            list(self.store.query('SELECT ?id ?weight WHERE { ?id name ?name . ?name weight ?weight }'))
        )
    
    def test_query_union(self):
        self.assertEqual(
            [('a', 'name-a', None), ('b', 'name-b', None), ('a', None, 'weight-a')],
            list(self.store.query('SELECT ?id ?name ?weight WHERE { { ?id name ?name} UNION {?id weight ?weight} }'))
        )
    
    def test_single_optional(self):
        self.assertEqual(
            [('a', 'name-a', 'weight-a'), ('b', 'name-b', None)],
            list(self.store.query('SELECT ?id ?value ?weight WHERE { ?id name ?value OPTIONAL {?id weight ?weight} }'))
        )
        self.assertEqual(
            [('b', 'name-b', None)],
            list(self.store.query('SELECT ?id ?value ?weight WHERE { ?id name ?value OPTIONAL {?id weight ?weight} ?id size ?size }'))
        )
    
    def test_multiple_optional(self):
        self.assertEqual(
            [('a', 'name-a', 'weight-a', None), ('b', 'name-b', None, 'size-b')],
            list(self.store.query('''SELECT ?id ?value ?weight ?size
                        WHERE { ?id name ?value 
                        OPTIONAL {?id weight ?weight}
                        OPTIONAL {?id size ?size} }'''))
        )

    def test_group_optional(self):
        self.assertEqual(
            [('a', 'name-a', None, None), ('b', 'name-b', None, None)],
            list(self.store.query('''SELECT ?id ?value ?weight ?size
                        WHERE { ?id name ?value 
                        OPTIONAL {?id weight ?weight . ?id size ?size} }'''))
        )
    
    def test_star_has_right_column_order(self):
        q = self.store.query('SELECT * WHERE { ?id name ?name }')
        self.assertEqual(('id', 'name'), tuple(v.name for v in q.variables))
        q = self.store.query('SELECT * WHERE { { ?id name ?name} UNION {?id weight ?weight} }')
        self.assertEqual(('id', 'name', 'weight'), tuple(v.name for v in q.variables))
        q = self.store.query('SELECT * WHERE { ?id name ?value OPTIONAL {?id weight ?weight} }')
        self.assertEqual(('id', 'value', 'weight'), tuple(v.name for v in q.variables))
    
    def test_filter(self):
        self.assertEqual(
            [(100,)],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height > 99) }'))
        )
        self.assertEqual(
            [],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height > 100) }'))
        )
        self.assertEqual(
            [(100,)],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height >= 100) }'))
        )
        self.assertEqual(
            [],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height >= 101) }'))
        )
        self.assertEqual(
            [(100,)],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height < 101) }'))
        )
        self.assertEqual(
            [],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height < 100) }'))
        )
        self.assertEqual(
            [(100,)],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height <= 100) }'))
        )
        self.assertEqual(
            [],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height <= 99) }'))
        )
        self.assertEqual(
            [],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height != 100) }'))
        )
        self.assertEqual(
            [(100,)],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height != 101) }'))
        )
        self.assertEqual(
            [],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height = 101) }'))
        )
        self.assertEqual(
            [(100,)],
            list(self.store.query('SELECT ?height WHERE { ?id height ?height FILTER (?height = 100) }'))
        )
        
    def test_order_by(self):
        self.assertEqual(
            [('a', 'name-a'), ('b', 'name-b')],
            list(self.store.query('SELECT ?id ?name WHERE { ?id name ?name } ORDER BY ?name'))
        )
        self.assertEqual(
            [('a', 'name-a'), ('b', 'name-b')],
            list(self.store.query('SELECT ?id ?name WHERE { ?id name ?name } ORDER BY ASC(?name)'))
        )
        self.assertEqual(
            [('b', 'name-b'), ('a', 'name-a')],
            list(self.store.query('SELECT ?id ?name WHERE { ?id name ?name } ORDER BY DESC(?name)'))
        )
        
    def test_limit(self):
        self.assertEqual(
            [('a', 'name-a')],
            list(self.store.query('SELECT ?id ?name WHERE { ?id name ?name } ORDER BY ?name LIMIT 1'))
        )
    
    def test_order_by(self):
        self.assertEqual(
            [('b', 'name-b')],
            list(self.store.query('SELECT ?id ?name WHERE { ?id name ?name } ORDER BY ?name OFFSET 1'))
        )
    
    def test_distinct(self):
        self.assertEqual(
            set([('a',), ('b',)]),
            set(self.store.query('SELECT DISTINCT ?id WHERE { { ?id name ?name} UNION {?id weight ?weight} }'))
        )



class TestIndex(unittest.TestCase):
    
    def setUp(self):
        self.index = Index([0, 1, 2])
        self.index2 = Index([2, 0, 1])
    
    def test___create_key(self):
        self.assertEqual(('a', 'b', 'c'), self.index._create_key(('a', 'b', 'c')))
        self.assertEqual(('c', 'a', 'b'), self.index2._create_key(('a', 'b', 'c')))
    
    def test_insert(self):
        self.index.insert(('a', 'b', 'c'))
        self.assertEqual({ 'a': { 'b': { 'c': ('a', 'b', 'c') } } },
                         self.index._index)
        
        self.index2.insert(('a', 'b', 'c'))
        self.assertEqual({ 'c': { 'a': { 'b': ('a', 'b', 'c') } } },
                         self.index2._index)
    
    def _check_match_full(self, index):
        index.insert(('a', 'b', 'c'))
        index.insert(('c', 'c', 'c'))
        index.insert(('a', 'b', 'b'))
        self.assertEqual(
            [('a', 'b', 'c')],
            list(index.match(('a', 'b', 'c')))
        )
        self.assertEqual(
            [],
            list(index.match(('a', 'b', 'd')))
        )
        self.assertEqual(
            [],
            list(index.match(('a', 'd', 'c')))
        )
        self.assertEqual(
            [],
            list(index.match(('d', 'b', 'c')))
        )
    
    def test_match_full(self):
        self._check_match_full(self.index)
        self._check_match_full(self.index2)
    
    def test_match_partial(self):
        self.index.insert(('a', 'b', 'c'))
        self.index.insert(('c', 'c', 'c'))
        self.index.insert(('a', 'b', 'b'))
        self.index.insert(('a', 'a', 'b'))
        
        self.assertEqual(
            set([('a', 'b', 'c'),
                 ('a', 'b', 'b')]),
            set(self.index.match(('a', 'b', None)))
        )
        self.assertEqual(
            set([('a', 'b', 'c'),
                 ('a', 'b', 'b'),
                 ('a', 'a', 'b')]),
            set(self.index.match(('a', None, None)))
        )
        self.assertEqual(
            set([('a', 'b', 'c'),
                 ('c', 'c', 'c'),
                 ('a', 'b', 'b'),
                 ('a', 'a', 'b')]),
            set(self.index.match((None, None, None)))
        )
    
    def test_key_error_if_not_indexed(self):
        self.index2.insert(('a', 'b', 'c'))
        self.index2.insert(('c', 'c', 'c'))
        self.index2.insert(('a', 'b', 'b'))
        self.index2.insert(('a', 'a', 'b'))
        
        self.assertEqual(
            set([('a', 'b', 'c')]),
            set(self.index2.match(('a', None, 'c')))
        )
        
        try:
            set(self.index2.match(('a', 'b', None)))
            self.fail('This index should not work with provided match')
        except LookupError:
            pass
        
        try:
            set(self.index2.match((None, 'b', 'c')))
            self.fail('This index should not work with provided match')
        except LookupError:
            pass
    

if __name__ == '__main__':
    unittest.main()