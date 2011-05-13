from pyparsing import Word, OneOrMore, alphas, Combine, Regex, Group, Literal, \
                      Optional, ZeroOrMore

variable = Combine('?' + Word(alphas))
variables = OneOrMore(variable)

literal = Regex(r'[^\s]+')
triple_value = variable | literal

triple = Group(triple_value + triple_value + triple_value + Optional(Literal('.').suppress()))
triples = OneOrMore(triple)

prefix = Group('PREFIX' + literal + literal)

prologue = ZeroOrMore(prefix)

select_query = 'SELECT' + Group(variables) + 'WHERE' + Literal('{').suppress() + \
            Group(triples) + \
       Literal('}').suppress()

query = Group(prologue) + Group(select_query)

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
        print query.parseString(q)