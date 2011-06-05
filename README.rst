===========
Mini Sparql
===========

Mini sparql is an experiment in writing a simple (in memory) triple store.  It can be used to read in files or triple data, which can be queried using sparql.  It's by no means complete, but does provide most of sparql 1.0.

Examples
========

Assuming you have triple data like::

    robin name Robin .
    robin size small .
    robin color red .
    robin color brown .
    robin legs 2 .
    sparrow name Sparrow .
    sparrow size small .
    sparrow color brown .
    bluetit name Bluetit .
    bluetit size small .
    bluetit color blue .
    bluetit color green .
    eagle name Eagle .
    eagle size large .
    eagle color brown .

In a file called birds.ttl, then you can run minisparql and query the data::

    $ python minisparql.py birds.ttl 
    sparql> SELECT ?name ?color WHERE { ?id name ?name . ?id color ?color }
    name, color
    'Bluetit', 'blue'
    'Bluetit', 'green'
    'Eagle', 'brown'
    'Robin', 'brown'
    'Robin', 'red'
    'Sparrow', 'brown'
    sparql> SELECT ?name WHERE { ?id name ?name . ?id color red }
    name
    'Robin'

Filters are supported too::

    sparql> SELECT ?name WHERE { ?id name ?name FILTER regex(?name, "r", "i") }
    name
    'Robin'
    'Sparrow'

As well as using the interactive prompt it is possible to execute queries via the -e switch::

    $ python minisparql.py birds.ttl -e 'SELECT ?name WHERE { ?id name ?name FILTER regex(?name, "r", "i") }'
    name
    'Robin'
    'Sparrow'
