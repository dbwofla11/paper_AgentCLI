(async()=>{
 const originalFetch=window.fetch, originalTimeout=window.setTimeout;
 const assert=(value,message)=>{if(!value)throw Error(message)};
 const button=[...document.querySelectorAll('.review-action')].find(x=>x.textContent==='리뷰 시작');
 const paper=papers.find(p=>p.slug===button.dataset.reviewSlug);
 const status=button.parentElement.querySelector('.link-status');
 let polled=0,posts=0,mode='failed',selected=[];
 window.setTimeout=(fn,ms,...args)=>originalTimeout(fn,ms===1500?1:ms,...args);
 window.fetch=async(url,options={})=>{
   if(url==='/api/status')return {ok:true,json:async()=>({ready:true,runner:'codex-cli'})};
   if(url==='/api/reviews'){posts++;return {ok:true,json:async()=>({job:{job_id:'mock-current'}})};}
   if(url.startsWith('/api/reviews/')){polled++;return {ok:true,json:async()=>({jobs:mode==='empty'?[]:[{job_id:'old-job',status:'running'},{job_id:'mock-current',status:'failed',message:'mock failure'}]})};}
   throw Error('Unexpected request '+url);
 };
 try{
   await startReview(paper,status,button);
   await new Promise(resolve=>originalTimeout(resolve,40));
   assert(!button.disabled,'failed job button remains disabled');
   assert(status.textContent.includes('mock failure'),'did not select current job ID');
   mode='empty';await startReview(paper,status,button);
   await new Promise(resolve=>originalTimeout(resolve,40));
   assert(!button.disabled,'missing job button remains disabled');
   assert(status.textContent.includes('찾을 수 없습니다'),'missing job has no explanation');
   window.fetch=async()=>({ok:false,status:503,json:async()=>({error:'mock unavailable'})});
   await startReview(paper,status,button);
   assert(!button.disabled&&status.textContent.includes('mock unavailable'),'server error');
   return {passed:5,mockedPosts:posts,mockedPolls:polled,actualReviewStarted:false};
 }finally{window.fetch=originalFetch;window.setTimeout=originalTimeout;reviewStates.delete(paper.slug);render();}
})()
