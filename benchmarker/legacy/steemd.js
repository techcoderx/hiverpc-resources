const steem = require('@hiveio/hive-js')

steem.api.setOptions({ url: 'http://192.168.1.4:8091', useAppbaseApi: true })

let user = 'techcoderx'

let startTime = new Date().getTime()
let lastTime = new Date().getTime()

console.log()
console.log('Welcome to AppBase steemd API Benchmark')
console.log()

steem.api.getDynamicGlobalProperties(() => {
    console.log('getDynamicGlobalProperties: ' + (new Date().getTime() - lastTime) + 'ms')
    setLastTime()
    steem.api.getConfig(() => {
        console.log('getConfig: ' + (new Date().getTime() - lastTime) + 'ms')
        setLastTime()
        steem.api.getAccounts([user],() => {
            console.log('getAccounts: ' + (new Date().getTime() - lastTime) + 'ms')
            setLastTime()
            steem.api.getAccountHistory(user,-1,100,() => {
                console.log('getAccountHistory: ' + (new Date().getTime() - lastTime) + 'ms')
                setLastTime()
                steem.api.getOrderBook(20, () => {
                    console.log('getOrderBook: ' + (new Date().getTime() - lastTime) + 'ms')
                    setLastTime()
                    endBenchmark()
                })
            })
        })
    })
})

function setLastTime() {
    lastTime = new Date().getTime()
}

function endBenchmark() {
    console.log()
    console.log('Total benchmark time: ' + (lastTime - startTime) + 'ms')
    console.log()
}
