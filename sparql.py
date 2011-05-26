from pyparsing import Word, OneOrMore, alphas, Combine, Regex, Group, Literal, \
                      Optional, ZeroOrMore, CaselessKeyword, Keyword, Forward, \
                      delimitedList, ParseException, QuotedString

import sys
import operator
from itertools import islice

_float = Regex(r'[-+]?\d+\.\d*([eE]\d+)?').setParseAction(lambda s, loc, toks: float(toks[0]))
_integer = Regex(r'[-+]?\d+').setParseAction(lambda s, loc, toks: int(toks[0]))
_number = _float | _integer
_string = QuotedString('"""', escChar='\\', multiline=True) \
        | QuotedString('\'\'\'', escChar='\\', multiline=True) \
        | QuotedString('"', escChar='\\') | QuotedString('\'', escChar='\\')
_full_iri = QuotedString('<', endQuoteChar='>')
_iri = _full_iri | Combine(Word(alphas) + ':' + Word(alphas))
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

def _query_parser(store):
    prefixes = {}
    
    def add_prefix(prefix, iri):
        prefixes[prefix] = iri
    
    def insert_prefixes(pattern):
        return tuple(insert_prefix(p) for p in pattern)
    
    def insert_prefix(p):
        if isinstance(p, LiteralExpression):
            value = p.value
            if isinstance(value, basestring):
                for prefix in prefixes:
                    if value.startswith(prefix):
                        iri = prefixes[prefix]
                        p.value = iri + value[len(prefix):]
                        break
        return p
    
    variable = Combine(Literal('?').suppress() + Word(alphas)) \
                .setParseAction(lambda s, loc, toks: VariableExpression(toks[0]))
    variables = OneOrMore(variable)
    
    literal = _literal.copy().setParseAction(lambda s, loc, toks: LiteralExpression(toks[0]))
    
    triple_value = variable | literal
    
    def group_if_multiple(s, loc, toks):
        if len(toks) > 1:
            return PatternGroup(toks)
        return toks
    
    triple = (triple_value + triple_value + triple_value)\
                .setParseAction(lambda s, loc, toks: Pattern(store, *(insert_prefixes(toks))))
    triples_block = delimitedList(triple,
                        delim=Optional(Literal('.').suppress())) \
                        .setParseAction(group_if_multiple) \
                        + Optional(Literal('.').suppress())
    
    group_pattern = Forward().setParseAction(group_if_multiple)
    
    def possible_union_group(s, loc, toks):
        if len(toks) == 3:
            return UnionGroup(toks[0], toks[-1])
        return toks
    
    group_or_union_pattern = (group_pattern + Optional(CaselessKeyword('UNION') + group_pattern)) \
                                .setParseAction(possible_union_group)
    optional_graph_pattern = (CaselessKeyword('OPTIONAL').suppress() + group_pattern) \
                                .setParseAction(lambda s, loc, toks: OptionalGroup(toks[0]))
    
    binary_operator = _create_binary_operator()
    
    binary_expression = (triple_value + binary_operator + triple_value) \
                            .setParseAction(lambda s, loc, toks: BooleanExpression(*toks))
    
    filter_expression = Literal('(').suppress() + binary_expression + Literal(')').suppress()
    
    filter_pattern = (CaselessKeyword('FILTER').suppress() + filter_expression) \
                        .setParseAction(lambda s, loc, toks: Filter(toks[0]))
    
    not_triples_pattern = optional_graph_pattern | group_or_union_pattern | filter_pattern
    
    group_pattern << (Literal('{').suppress() + \
                      (Optional(triples_block) + ZeroOrMore(not_triples_pattern) + Optional(triples_block)) + \
                      Literal('}').suppress())
    
    prefix = Group(CaselessKeyword('PREFIX').suppress() +
                    (Combine(Word(alphas) + ':').setResultsName('name') + _full_iri.setResultsName('value'))\
                        .setParseAction(lambda s, loc, toks: add_prefix(toks[0], toks[1]))
                  )

    prologue = Group(ZeroOrMore(prefix).setResultsName('prefixes')).setResultsName('prologue')
    
    order_by = CaselessKeyword('ORDER').suppress() + CaselessKeyword('BY').suppress() + \
               (
                (
                    (CaselessKeyword('ASC') | CaselessKeyword('DESC'))
                   + Literal('(').suppress() + variable + Literal(')').suppress()
                )
                
                | variable
               ).setParseAction(
                    lambda s, loc, toks: OrderBy(toks[-1], len(toks) == 1 or toks[0].upper() != 'DESC')
               )
    
    limit = (CaselessKeyword('LIMIT').suppress() + Regex(r'\d+').setParseAction(lambda s, loc, toks: Limit(toks[0])))
    offset = (CaselessKeyword('OFFSET').suppress() + Regex(r'\d+').setParseAction(lambda s, loc, toks: Offset(toks[0])))
    
    select_query = CaselessKeyword('SELECT') + \
                   Group(variables | Keyword('*')) + \
                   CaselessKeyword('WHERE').suppress() + group_pattern + \
                   Optional(order_by) + \
                   ((Optional(limit) + Optional(offset)) \
                  | (Optional(offset) + Optional(limit)))

    query = prologue + Group(select_query).setResultsName('query')
    return query


def _uniq(l):
    seen = set()
    u = []
    for i in l:
        if i not in seen:
            u.append(i)
            seen.add(i)
    return u

class SelectQuery(object):
    def __init__(self, name, variables, patterns, order_by, limit, offset):
        self.name = name
        if len(variables) == 1 and variables[0] == '*':
            variables = patterns.variables
        self.variables = tuple(_uniq(variables))
        self.patterns = patterns
        self.order_by = order_by
        self.limit = limit
        self.offset = offset or 0
    
    def __iter__(self):
        variables = self.variables
        matches = self.patterns.match({})
        if self.order_by is not None:
            matches = self.order_by.order(matches)
        
        stop = None
        if self.limit is not None:
            stop = self.offset + self.limit
        
        matches = islice(matches, self.offset, stop)
        
        for match in matches:
            yield tuple(v.resolve(match) for v in variables)


class Pattern(object):
    def __init__(self, store, a, b, c):
        self.store = store
        self.pattern = (a, b, c)
    
    @property
    def variables(self):
        return [v for v in self.pattern if getattr(v, 'name', None)]
    
    def match(self, solution=None):
        for m in self.store.match_triples(self.pattern, solution):
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


class Expression(object):
    pass


class BooleanExpression(Expression):
    def __init__(self, lhs, operator, rhs):
        self.lhs = lhs
        self.operator = operator
        self.rhs = rhs
    
    def matches(self, solution):
        a = self.lhs.resolve(solution)
        b = self.rhs.resolve(solution)
        return self.operator(a, b)
    
    def __repr__(self):
        return u'%s %s %s' % (self.lhs, self.operator.__name__, self.rhs)


class VariableExpression(Expression):
    def __init__(self, name):
        self.name = name
    
    def resolve(self, solution):
        return solution.get(self.name)
    
    def __eq__(self, other):
        return self.name == getattr(other, 'name', None)
    
    def __hash__(self):
        return hash(self.name)
    
    def __repr__(self):
        return u'VariableExpression(%s)' % self.name


class LiteralExpression(Expression):
    def __init__(self, value):
        self.value = value
    
    def resolve(self, solution):
        return self.value
    
    def __repr__(self):
        return u'LiteralExpression(%s)' % self.value


class OrderBy(object):
    def __init__(self, expression, asc):
        self.expression = expression
        self.asc = asc
    
    def _key(self, solution):
        return self.expression.resolve(solution)
    
    def order(self, matches):
        return sorted(matches, key=self._key, reverse=(not self.asc))

class Limit(object):
    def __init__(self, limit):
        self.limit = int(limit)

class Offset(object):
    def __init__(self, offset):
        self.offset = int(offset)

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
        key = self._create_key(tuple(t.resolve({}) for t in triple))
        return self._match(self._index, key)
    
    def _match_remaining(self, index, key):
        if key[0] is not None:
            raise LookupError(key)
        for v in index.values():
            if getattr(v, 'values', None) is not None:
                for m in self._match_remaining(v, key[1:]):
                    yield m
            else:
                yield v
    
    def _match(self, index, key):
        if key[0] is None:
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


class TripleStore(object):
    
    def __init__(self):
        self._triples = []
    
    def add_triples(self, *triples):
        self._triples.extend(triples)

    def clear_triples(self):
        self._triples = []

    def match_triples(self, pattern, existing=None):
        if existing is None:
            existing = {}
        triple = tuple(a.resolve(existing) for a in pattern)
        for a, b, c in self._triples:
            if _matches(triple, (a, b, c)):
                matches = _get_matches(pattern, (a, b, c))
                matches.update(existing)
                yield matches
    
    def parse_query(self, q):
        _qp = _query_parser(self)

        return _qp.parseString(q)

    def query(self, q):
        p = self.parse_query(q)
        q = p.query
        name = q[0]
        variables = q[1]
        patterns = q[2]
        
        order_by = None
        limit = None
        offset = None
        
        for modifier in q[3:]:
            if isinstance(modifier, OrderBy):
                order_by = modifier
            elif isinstance(modifier, Limit):
                limit = modifier.limit
            elif isinstance(modifier, Offset):
                offset = modifier.offset
        
        return SelectQuery(name, variables, patterns, order_by, limit, offset)
    
    def import_file(self, filename):
        triple = Group(_literal + _literal + _literal + Literal('.').suppress())

        turtle = ZeroOrMore(triple)
        
        print 'Importing', filename, '...',
        sys.stdout.flush()
        
        turtle = turtle.parseWithTabs()
        from mmap import mmap
        f = open(filename, 'r+b')
        try:
            m = mmap(f.fileno(), 0)
            try:
                self.add_triples(*turtle.parseString(m, parseAll=True))
            finally:
                m.close()
        finally:
            f.close()
        print 'done'
            


def _matches(pattern, triple):
    for p, t in zip(pattern, triple):
        if not(p is None or p == t):
            return False
    return True


def _get_matches(pattern, triple):
    return dict((getattr(a, 'name'), b) for (a,b) in zip(pattern, triple) if getattr(a, 'name', None))


def run_prompt(store):
    import cmd
    class Sparql(cmd.Cmd):
        prompt='sparql> '
        
        def default(self, line):
            try:
                q = store.query(line)
                print q.variables
                for row in q:
                    print row
            except ParseException, p:
                print p
    
    s = Sparql()
    s.cmdloop()

if __name__ == '__main__':
    store = TripleStore()
    if len(sys.argv) > 1:
        store.import_file(sys.argv[1])
    run_prompt(store)