from pyparsing import Word, OneOrMore, alphas, Combine, Regex, Group, Literal, \
                      Optional, ZeroOrMore, Keyword, Forward, delimitedList

def _query_parser():
    variable = Combine('?' + Word(alphas))
    variables = OneOrMore(variable)

    literal = Regex(r'[^\s{}]+')
    triple_value = variable | literal
    
    triple = Group(triple_value + triple_value + triple_value)
    triples_block = delimitedList(triple,
                        delim=Optional(Literal('.').suppress()))  + Optional(Literal('.').suppress())
    
    group_pattern = Forward()
    
    group_or_union_pattern = group_pattern + Optional(Keyword('UNION') + group_pattern)
    optional_graph_pattern = Keyword('OPTIONAL') + group_pattern
    
    not_triples_pattern = optional_graph_pattern | group_or_union_pattern
    
    group_pattern << (Literal('{').suppress() + \
                      Group(ZeroOrMore(triples_block) + ZeroOrMore(not_triples_pattern) + ZeroOrMore(triples_block)) + \
                      Literal('}').suppress())
    
    prefix = Group(Keyword('PREFIX').suppress() + literal.setResultsName('name') + literal.setResultsName('value'))

    prologue = Group(ZeroOrMore(prefix).setResultsName('prefixes')).setResultsName('prologue')

    select_query = Keyword('SELECT') + Group(variables) + Keyword('WHERE').suppress() + group_pattern

    query = prologue + Group(select_query).setResultsName('query')
    return query

_qp = _query_parser()

def parse_query(q):
    return _qp.parseString(q)

_triples = []

def add_triples(*triples):
    _triples.extend(triples)

def _matches(triple1, triple2):
    for t1, t2 in zip(triple1, triple2):
        if t1 != t2 and not t1.startswith('?'):
            return False
    return True

def _var_name(name):
    if name.startswith('?'):
        return name[1:]
    return None

def _get_matches(pattern, triple):
    return dict((_var_name(a), b) for (a,b) in zip(pattern, triple) if _var_name(a))

def match_triples(pattern, existing=None):
    if existing is None:
        existing = {}
    triple = tuple(existing.get(_var_name(a), a) for a in pattern)
    for a, b, c in _triples:
        if _matches(triple, (a, b, c)):
            matches = _get_matches(pattern, (a, b, c))
            matches.update(existing)
            yield matches

def _join(previous, pattern):
    for p in previous:
        for match in match_triples(pattern, p):
            yield match

def _union(previous, patterns):
    for p in previous:
        yield p
    for p in _group(patterns):
        yield p

def _optional(previous, pattern):
    for p in previous:
        matched = False
        for match in match_triples(pattern, p):
            yield match
            matched = True
        if not matched:
            yield p
        

def is_group(pattern):
    if isinstance(pattern, basestring):
        return False
    if len(pattern) != 3:
        return True
    if isinstance(pattern[0], basestring):
        return False
    return False

def print_patterns(patterns):
    for pattern in patterns:
        if is_group(pattern):
            print_patterns(pattern)
        else:
            print pattern

def _group(patterns, previous=None, union=False, optional=False):
    for pattern in patterns:
        if is_group(pattern):
            previous = _group(pattern, previous, union, optional)
        else:
            if previous is None:
                previous = match_triples(pattern)
            elif pattern == 'UNION':
                union = True
            elif pattern == 'OPTIONAL':
                optional = True
            elif union:
                previous = _union(previous, patterns)
                break
            elif optional:
                previous = _optional(previous, pattern)
                optional = False
            else:
                previous = _join(previous, pattern)
    return previous
    

def query(q):
    p = parse_query(q)
    name, variables, patterns = p.query
    
    #print_patterns(patterns)
    
    for match in _group(patterns):
        yield tuple(match.get(_var_name(v)) for v in variables)

if __name__ == '__main__':
    queries = [
        """SELECT ?title
        WHERE
        {
          <http://example.org/book/book1> <http://purl.org/dc/elements/1.1/title> ?title .
        }""",
        """PREFIX foaf:   <http://xmlns.com/foaf/0.1/>
        SELECT ?x ?name
        WHERE  { ?x foaf:name ?name }""",
        
        """PREFIX foaf:    <http://xmlns.com/foaf/0.1/>
        SELECT ?name ?mbox
        WHERE  {
                  ?x foaf:name ?name .
                  ?x foaf:mbox ?mbox .
               }""",
        
        """PREFIX dc10:  <http://purl.org/dc/elements/1.0/>
           PREFIX dc11:  <http://purl.org/dc/elements/1.1/>

           SELECT ?title
           WHERE  { { ?book dc10:title  ?title } UNION { ?book dc11:title  ?title } }"""
    ]
    for q in queries:
        print q
        print parse_query(q)
    
    add_triples(('a', 'name', 'c'),
                ('b', 'name', 'd'),
                ('a', 'weight', 'c'),
                ('c', 'weight', '5'),
                ('b', 'size', 'one'))
    
    print list(query('SELECT ?id ?value WHERE { ?id name ?value }'))
    print list(query('SELECT ?id ?value WHERE { ?id name ?value . ?id weight ?value }'))
    print list(query('SELECT ?id ?weight WHERE { ?id name ?value . ?value weight ?weight }'))
    print list(query('SELECT ?id ?value WHERE { { ?id name ?value} UNION {?id weight ?value} }'))
    print list(query('SELECT ?id ?value ?weight WHERE { ?id name ?value OPTIONAL {?id weight ?weight} }'))
    print list(query('''SELECT ?id ?value ?weight ?size
                    WHERE { ?id name ?value 
                    OPTIONAL {?id weight ?weight}
                    OPTIONAL {?id size ?size} }'''))