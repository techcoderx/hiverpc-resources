const steem = require('steem')

steem.api.setOptions({ url: 'http://192.168.0.186:8093', useAppbaseApi: true })

let user = 'techcoderx'
let queryTag = ''
let discussionLimit = 20

let startTime = new Date().getTime()
let lastTime = new Date().getTime()

console.log()
console.log('Welcome to AppBase hive API Benchmark')
console.log()

steem.api.getDiscussionsByTrending({tag:queryTag,limit:discussionLimit},(err,res) => {
    console.log('getDiscussionsByTrending: ' + (new Date().getTime() - lastTime) + 'ms')
    setLastTime()
    steem.api.getDiscussionsByFeed({tag:user,limit:discussionLimit}, function(err, result) {
        console.log('getDiscussionsByFeed: ' + (new Date().getTime() - lastTime) + 'ms')
        setLastTime()
        steem.api.getDiscussionsByHot({tag:queryTag,limit:discussionLimit}, function(err, result) {
            console.log('getDiscussionsByHot: ' + (new Date().getTime() - lastTime) + 'ms')
            setLastTime()
            steem.api.getDiscussionsByCreated({tag:queryTag,limit:discussionLimit},() => {
                console.log('getDiscussionsByCreated: ' + (new Date().getTime() - lastTime) + 'ms')
                setLastTime()
                steem.api.getDiscussionsByBlog({tag:user,limit:discussionLimit}, function(err, result) {
                    console.log('getDiscussionsByBlog: ' + (new Date().getTime() - lastTime) + 'ms')
                    setLastTime()
                    console.log()
                    console.log('Total benchmark time: ' + (lastTime - startTime) + 'ms')
                    console.log()
                })
            })
        })
    })
})

function setLastTime() {
    lastTime = new Date().getTime()
}