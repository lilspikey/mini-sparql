from pyparsing import Word, OneOrMore, alphas, Combine, Regex, Group, Literal, \
                      Optional, ZeroOrMore, Keyword, Forward, delimitedList, \
                      ParseException, QuotedString

import sys
import operator

_number = Regex(r'[-+]?\d+(\.\d*)?([eE]\d+)?').setParseAction(lambda s, loc, toks: float(toks[0]))
_string = QuotedString('"""', escChar='\\', multiline=True) \
        | QuotedString('\'\'\'', escChar='\\', multiline=True) \
        | QuotedString('"', escChar='\\') | QuotedString('\'', escChar='\\')
_iri = QuotedString('<', unquoteResults=False, endQuoteChar='>') | Combine(Word(alphas) + ':' + Word(alphas))
_boolean = (Keyword('true') | Keyword('false')).setParseAction(lambda s, loc, toks: toks[0] == 'true')

_literal = _number | _string | _iri | _boolean | Word(alphas)

def _create_binary_operator():
    existing = None
    for symbol, op in (('<=', operator.le), ('>=', operator.ge),
                       ('<', operator.lt), ('>', operator.gt),
                       ('=', operator.eq), ('!=', operator.ne)):
        bop = _operator_keyword(symbol, op)
        if not existing:
            existing = bop
        else:
            existing = existing | bop
    return existing

def _operator_keyword(symbol, op):
    return Keyword(symbol).setParseAction(lambda s, loc, toks: op)

def _query_parser():
    variable = Combine('?' + Word(alphas))
    variables = OneOrMore(variable)

    triple_value = variable | _literal
    
    def group_if_multiple(s, loc, toks):
        if len(toks) > 1:
            return PatternGroup(toks)
        return toks
    
    triple = (triple_value + triple_value + triple_value)\
                .setParseAction(lambda s, loc, toks: Pattern(*toks))
    triples_block = delimitedList(triple,
                        delim=Optional(Literal('.').suppress())) \
                        .setParseAction(group_if_multiple) \
                        + Optional(Literal('.').suppress())
    
    group_pattern = Forward().setParseAction(group_if_multiple)
    
    def possible_union_group(s, loc, toks):
        if len(toks) == 3:
            return UnionGroup(toks[0], toks[-1])
        return toks
    
    group_or_union_pattern = (group_pattern + Optional(Keyword('UNION') + group_pattern)) \
                                .setParseAction(possible_union_group)
    optional_graph_pattern = (Keyword('OPTIONAL').suppress() + group_pattern) \
                                .setParseAction(lambda s, loc, toks: OptionalGroup(toks[0]))
    
    binary_operator = _create_binary_operator()
    
    binary_expression = (triple_value + binary_operator + triple_value) \
                            .setParseAction(lambda s, loc, toks: BinaryExpression(*toks))
    
    filter_expression = Literal('(').suppress() + binary_expression + Literal(')').suppress()
    
    filter_pattern = (Keyword('FILTER').suppress() + filter_expression) \
                        .setParseAction(lambda s, loc, toks: Filter(toks[0]))
    
    not_triples_pattern = optional_graph_pattern | group_or_union_pattern | filter_pattern
    
    group_pattern << (Literal('{').suppress() + \
                      (Optional(triples_block) + ZeroOrMore(not_triples_pattern) + Optional(triples_block)) + \
                      Literal('}').suppress())
    
    prefix = Group(Keyword('PREFIX').suppress() + Combine(Word(alphas) + ':').setResultsName('name') + QuotedString('<', unquoteResults=False, endQuoteChar='>').setResultsName('value'))

    prologue = Group(ZeroOrMore(prefix).setResultsName('prefixes')).setResultsName('prologue')

    select_query = Keyword('SELECT') + Group(variables | Keyword('*')) + Keyword('WHERE').suppress() + group_pattern

    query = prologue + Group(select_query).setResultsName('query')
    return query

_qp = _query_parser()

def parse_query(q):
    return _qp.parseString(q)

_triples = []

def add_triples(*triples):
    _triples.extend(triples)

def clear_triples():
    global _triples
    _triples = []

def _matches(triple1, triple2):
    for t1, t2 in zip(triple1, triple2):
        if t1 != t2 and not t1.startswith('?'):
            return False
    return True

def _var_name(name):
    if isinstance(name, basestring) and name.startswith('?'):
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

def query(q):
    p = parse_query(q)
    name, variables, patterns = p.query
    
    return SelectQuery(name, variables, patterns)

def _uniq(l):
    seen = set()
    u = []
    for i in l:
        if i not in seen:
            u.append(i)
            seen.add(i)
    return u

class SelectQuery(object):
    def __init__(self, name, variables, patterns):
        self.name = name
        if len(variables) == 1 and variables[0] == '*':
            variables = patterns.variables
        self.variables = tuple(_uniq(variables))
        self.patterns = patterns
    
    def __iter__(self):
        variables = self.variables
        
        for match in self.patterns.match({}):
            yield tuple(match.get(_var_name(v)) for v in variables)

class Pattern(object):
    def __init__(self, a, b, c):
        self.pattern = (a, b, c)
    
    @property
    def variables(self):
        return [v for v in self.pattern if v.startswith('?')]
    
    def match(self, solution=None):
        for m in match_triples(self.pattern, solution):
            yield m
    
    def __repr__(self):
        return 'Pattern(%s, %s, %s)' % self.pattern

class PatternGroup(object):
    def __init__(self, patterns):
        self.patterns = patterns
    
    @property
    def variables(self):
        variables = []
        for p in self.patterns:
            variables.extend(p.variables)
        return variables
    
    def match(self, solution=None):
        joined = None
        for pattern in self.patterns:
            if joined is None:
                joined = pattern.match(solution)
            else:
                joined = self._join(joined, pattern)
        for m in joined:
            yield m
    
    def _join(self, matches, pattern):
        for m in matches:
            for m2 in pattern.match(m):
                yield m2
    
    def __repr__(self):
        return 'PatternGroup(%r)' % self.patterns


class OptionalGroup(object):
    def __init__(self, pattern):
        self.pattern = pattern
    
    @property
    def variables(self):
        return self.pattern.variables
    
    # just return untouched solution if nothing else matched
    def match(self, solution):
        matched = False
        for m in self.pattern.match(solution):
            yield m
            matched = True
        if not matched:
            yield solution
    
    def __repr__(self):
        return 'OptionalGroup(%r)' % self.pattern

class UnionGroup(object):
    def __init__(self, pattern1, pattern2):
        self.pattern1 = pattern1
        self.pattern2 = pattern2
    
    @property
    def variables(self):
        variables = []
        variables.extend(self.pattern1.variables)
        variables.extend(self.pattern2.variables)
        return variables
    
    def match(self, solution):
        for m in self.pattern1.match(solution):
            yield m
        for m in self.pattern2.match(solution):
            yield m
    
    def __repr__(self):
        return 'UnionGroup(%r, %r)' % (self.pattern1, self.pattern2)


class Filter(object):
    def __init__(self, expression):
        self.expression = expression

    @property
    def variables(self):
        return []

    def match(self, solution):
        try:
            if self.expression.matches(solution):
                yield solution
        except TypeError:
            pass

    def __repr__(self):
        return 'Filter(%r)' % (self.expression)


class BinaryExpression(object):
    def __init__(self, lhs, operator, rhs):
        self.lhs = lhs
        self.operator = operator
        self.rhs = rhs
    
    def _resolve(self, solution, a):
        name = _var_name(a)
        if name is None:
            return a
        return solution.get(name)
    
    def matches(self, solution):
        a = self._resolve(solution, self.lhs)
        b = self._resolve(solution, self.rhs)
        return self.operator(a, b)
    
    def __repr__(self):
        return u'%s %s %s' % (self.lhs, self.operator.__name__, self.rhs)

class Index(object):
    
    def __init__(self, permutation):
        self.permutation = permutation
        self._index = {}
    
    def _create_key(self, triple):
        return tuple(triple[i] for i in self.permutation)
    
    def insert(self, triple):
        key = self._create_key(triple)
        self._insert(self._index, key, triple)
    
    def _insert(self, index, key, triple):
        if len(key) == 1:
            index[key[0]] = triple
        else:
            try:
                subindex = index[key[0]]
            except KeyError:
                subindex = {}
                index[key[0]] = subindex
            self._insert(subindex, key[1:], triple)
    
    def match(self, triple):
        key = self._create_key(triple)
        return self._match(self._index, key)
    
    def _match_remaining(self, index, key):
        if _var_name(key[0]) is None:
            raise LookupError(key)
        for v in index.values():
            if getattr(v, 'values', None) is not None:
                for m in self._match_remaining(v, key[1:]):
                    yield m
            else:
                yield v
    
    def _match(self, index, key):
        name = _var_name(key[0])
        if name is not None:
            for m in self._match_remaining(index, key):
                yield m
        else:
            try:
                if len(key) == 1:
                    yield index[key[0]]
                else:
                    subindex = index[key[0]]
                    for m in self._match(subindex, key[1:]):
                        yield m
            except KeyError:
                pass

def import_file(filename):
    triple = Group(_literal + _literal + _literal + Literal('.').suppress())
    
    turtle = ZeroOrMore(triple)
    
    add_triples(*turtle.parseFile(filename, parseAll=True))

def run_prompt():
    import cmd
    class Sparql(cmd.Cmd):
        prompt='sparql> '
        
        def default(self, line):
            try:
                q = query(line)
                print q.variables
                for row in q:
                    print row
            except ParseException, p:
                print p
    
    s = Sparql()
    s.cmdloop()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        import_file(sys.argv[1])
    run_prompt()