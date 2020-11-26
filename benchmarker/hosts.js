const nodes = require('./nodes')
const iplookup = require('ip-locator')

for (let i = 0; i < nodes.length; i++)
    if (nodes[i].startsWith('https://'))
        iplookup.getDomainOrIPDetails(nodes[i].substr(8), 'json', (e,d) =>
            console.log(nodes[i].substr(8), d)
        )