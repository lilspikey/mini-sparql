from pyparsing import Word, OneOrMore, alphas, Combine, Regex, Group, Literal, \
                      Optional, ZeroOrMore

def _query_parser():
    variable = Combine('?' + Word(alphas))
    variables = OneOrMore(variable)

    literal = Regex(r'[^\s]+')
    triple_value = variable | literal

    triple = Group(triple_value + triple_value + triple_value + Optional(Literal('.').suppress()))
    triples = OneOrMore(triple)

    prefix = Group(Literal('PREFIX').suppress() + literal.setResultsName('name') + literal.setResultsName('value'))

    prologue = Group(ZeroOrMore(prefix).setResultsName('prefixes')).setResultsName('prologue')

    select_query = 'SELECT' + Group(variables) + Literal('WHERE').suppress() + Literal('{').suppress() + \
                Group(triples) + \
           Literal('}').suppress()

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

def query(q):
    p = parse_query(q)
    name, variables, patterns = p.query
    
    p = None
    for pattern in patterns:
        if p is None:
            p = match_triples(pattern)
        else:
            p = _join(p, pattern)
    
    for match in p:
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
               }"""
    ]
    for q in queries:
        print q
        print parse_query(q)
    
    add_triples(('a', 'name', 'c'), ('b', 'name', 'd'), ('a', 'weight', 'c'),
                ('c', 'weight', '5'))
    
    print list(query('SELECT ?id ?value WHERE { ?id name ?value }'))
    print list(query('SELECT ?id ?value WHERE { ?id name ?value . ?id weight ?value }'))
    print list(query('SELECT ?id ?weight WHERE { ?id name ?value . ?value weight ?weight }'))