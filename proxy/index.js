const Express = require('express')
const CORS = require('cors')
const bodyParser = require('body-parser')
const { v4: uuidv4 } = require('uuid')
const axios = require('axios')
const app = Express()
const config = require('./config.json') // https://github.com/ecency/rpc-proxy/blob/main/config.example.hive.json

const rawBodySaver = (req, res, buf, encoding) => {
    if (buf && buf.length)
        req.rawBody = buf.toString(encoding || 'utf8');
}

app.use(CORS())
app.use(bodyParser.json({ verify: rawBodySaver }));
app.use(bodyParser.urlencoded({ verify: rawBodySaver, extended: true }));
app.use(bodyParser.raw({ verify: rawBodySaver, type: '*/*' }));

// this should be deprecated decades ago, but for some reason they are still being used :\
const appbaseTranslator = (reqJson) => {
    if (reqJson.method !== 'call')
        return reqJson
    else if (!reqJson || !Array.isArray(reqJson.params) || reqJson.params.length !== 3)
        return null
    else return {
        id: 1,
        jsonrpc: '2.0',
        method: 'condenser_api.' + reqJson.params[1],
        params: reqJson.params[2]
    }
}

const parseError = () => {
    return {
        jsonrpc: '2.0',
        id: null,
        error: {
            code: -32700,
            messgae: 'Parse error',
            data: { error_id: uuidv4(), jussi_request_id: '0' }
        }
    }
}

const internalError = () => {
    return {
        jsonrpc: '2.0',
        id: null,
        error: {
            code: -32603,
            messgae: 'Internal server error',
            data: { error_id: uuidv4(), jussi_request_id: '0' }
        }
    }
}

// maybe we can serve a webpage here
app.get('/',(req,res) => res.send({ info: process.env.PROXY_INFO || 'This is a dead simple hive JSONRPC proxy powered by 69 lines of NodeJS node.', jussi_num: -1, status: 'OK' }))

// actual jsonrpc route
app.post('/',(req,res) => {
    let dataJson, target = null
    try {
        dataJson = appbaseTranslator(JSON.parse(req.rawBody))
    } catch (e) {
        return res.send(parseError())
    }
    if (dataJson === null)
        return res.send(parseError())
    for (let i in config.routes) if (new RegExp(i).test(dataJson.method)) {
        target = config.routes[i].target
        break
    }
    axios.post(config.targets[target],dataJson,{timeout:config.timeouts[target]*1000})
        .then((r) => res.send(r.data))
        .catch(() => res.send(internalError()))
    console.log(dataJson)
})

app.listen(process.env.PORT || 3030)
