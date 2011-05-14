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

def _matches(a0, a):
    return a0.startswith('?') or a0 == a

def query_by_example(a0, b0, c0):
    for a, b, c in _triples:
        if _matches(a0, a) and _matches(b0, b) and _matches(c0, c):
            yield a, b, c

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