const config = require('./config.json')

const monitor = async () => {
    try {
        const api = await fetch(config.rpc,{
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: 1,
                jsonrpc: '2.0',
                method: 'database_api.get_dynamic_global_properties',
                params: {}
            })
        })
        if (api.status >= 200 && api.status <= 299) {
            let result = await api.json()
            if (!result.error && typeof result.result.head_block_number === 'number' && new Date(result.result.time+'Z').getTime() > new Date().getTime() - 6000)
                await fetch(config.pushUrl)
        }
    } catch {}
}

monitor()
setInterval(monitor,config.intervalSeconds*1000)