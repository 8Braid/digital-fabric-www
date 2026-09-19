/* 8Braid measurement v1. Consent-first, allowlisted events; no form values. */
(function () {
  'use strict';
  if (window.braidAnalytics) return;
  var config = document.currentScript && document.currentScript.dataset;
  var id = config && config.measurementId;
  var site = config && config.site;
  var app = config && config.app === 'true';
  var hosts = { '8braid': ['8braid.com', 'www.8braid.com'], sovclear: ['sovclear.com', 'www.sovclear.com'], 'digital-fabric': ['digital-fabric.com', 'www.digital-fabric.com', 'old.digital-fabric.com'] };
  if (!id || !/^G-[A-Z0-9]+$/.test(id) || !hosts[site] || hosts[site].indexOf(location.hostname) < 0) return;
  var key = 'braid_analytics_consent_v1', choice = null, loaded = false, lastPage = '', elapsed = 0, engaged = false, depth = 0;
  var params = ['content_group','site_name','site_area','cta_name','cta_placement','destination_group','method','lead_type','section_name','form_name','step_name','error_category','workflow_name','article_slug','percent_scrolled'];
  var events = ['page_view','cta_click','contact_click','email_copy','portfolio_handoff','evidence_view','section_view','example_open','faq_open','article_engaged','scroll_depth','file_download','source_click','footnote_click','form_start','form_error','sign_up','login','auth_start','auth_code_sent','auth_error','onboarding_complete','workflow_start','workflow_complete','workflow_error','generate_lead','qualify_lead','close_convert_lead'];
  function readChoice() { try { var saved = JSON.parse(localStorage.getItem(key)); return saved && Date.now() - saved.at < 180 * 86400000 ? saved.value : null; } catch (_) { return null; } }
  choice = readChoice();
  function path() {
    var p = location.pathname;
    if (app) {
      var auth = /^\/auth\/(login(?:\/password|\/email)?|signup(?:\/email)?|context-picker|forgot-password|reset-password)\/?$/.exec(p);
      if (auth) return '/auth/' + auth[1];
      if (p === '/') return '/app';
      var feature = /^\/(intelligence|accounting|marketplace|contracts|deals|entities|field-ops|platform|research|threads|messages|settings|onboarding|production|workspace|wiki|compliance|security|views)(?:\/|$)/.exec(p);
      return feature ? '/app/' + feature[1] : '/app/other';
    }
    // Public pages only; URL queries and fragments never enter page_location.
    if (site === '8braid') {
      if (/^\/(?:technology|programmable-transactions|proofs|modalities|benchmarks|encryption|build|enterprise|personal|evidence|compare|defense|finance|privacy)?\/?$/.test(p)) return p;
      if (/^\/journal(?:\/series)?(?:\/[a-z0-9-]+)?\/?$/.test(p) && !/%|@/.test(p)) return p;
      if (p === '/authors/ashley-dunfield') return p;
    } else if (site === 'sovclear') {
      if (/^\/(?:index\.html|signin\.html|signup\.html|dashboard\.html|forgot-password\.html|verify-email\.html|eula-accept\.html|privacy\.html|docs\/(?:index\.html)?|trust\/(?:index\.html)?)?$/.test(p)) return p === '/index.html' ? '/' : p;
    } else if (/^\/(?:index\.html|claims\.html|explorer\.html|privacy\.html)?$/.test(p)) return p === '/index.html' ? '/' : p;
    return '/other';
  }
  function group(p) {
    if (app || /signin|signup|dashboard|verify-email|eula-accept|forgot-password/.test(p)) return 'application';
    if (/journal/.test(p)) return 'journal';
    if (/evidence|benchmarks|encryption|proofs|claims|explorer|trust/.test(p)) return 'evidence';
    if (/defense|finance|enterprise|build|personal/.test(p)) return 'use_case';
    return p === '/' ? 'home' : 'product';
  }
  function safeValue(v) { return typeof v === 'string' && /^[a-zA-Z0-9_./-]{1,100}$/.test(v) ? v : undefined; }
  function referrer() { try { var u = new URL(document.referrer); return u.protocol === 'https:' || u.protocol === 'http:' ? u.origin + '/' : ''; } catch (_) { return ''; } }
  function push() { window.dataLayer.push(arguments); }
  function send(name, extra) {
    if (choice !== 'accepted' || !loaded || events.indexOf(name) < 0) return;
    var p = path(), payload = { send_to: id, page_location: location.origin + p, page_title: site + ' | ' + p, page_referrer: lastPage || referrer(), content_group: group(p), site_name: site, site_area: app ? 'app' : 'website' };
    Object.keys(extra || {}).forEach(function (k) { if (params.indexOf(k) < 0) return; var v = safeValue(String(extra[k])); if (v !== undefined) payload[k] = v; });
    push('event', name, payload);
  }
  function page() {
    if (choice !== 'accepted' || !loaded) return;
    var current = location.origin + path();
    if (lastPage === current) return;
    elapsed = 0; engaged = false; depth = 0;
    push('set',{page_location:current,page_title:site+' | '+path(),page_referrer:lastPage||referrer()});
    send('page_view');
    if (group(path()) === 'evidence') send('evidence_view');
    lastPage = current;
    observeSections();
  }
  function load() {
    if (loaded || choice !== 'accepted') return;
    window.dataLayer = window.dataLayer || [];
    window.gtag = push;
    window['ga-disable-' + id] = false;
    push('consent','default',{analytics_storage:'granted',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});
    push('js',new Date());
    var options={send_page_view:false,allow_google_signals:false,allow_ad_personalization_signals:false,cookie_expires:15552000,cookie_update:false,page_location:location.origin+path(),page_title:site+' | '+path(),page_referrer:referrer()};
    var query=new URLSearchParams(location.search);
    ['source','medium','name','content','term'].forEach(function(k){var value=query.get('utm_'+(k==='name'?'campaign':k));if(value&&/^[a-zA-Z0-9_-]{1,80}$/.test(value))options['campaign_'+k]=value;});
    push('config',id,options);
    var s=document.createElement('script'); s.async=true; s.src='https://www.googletagmanager.com/gtag/js?id='+id; document.head.appendChild(s);
    loaded=true; page();
  }
  function clearCookies() {
    document.cookie.split(';').forEach(function (item) {
      var name=item.trim().split('=')[0]; if (!/^_ga(?:_|$)/.test(name)) return;
      ['',location.hostname,'.'+location.hostname,location.hostname.replace(/^www\./,''),'.'+location.hostname.replace(/^www\./,'')].forEach(function (d) { document.cookie=name+'=; Max-Age=0; path=/'+(d?'; domain='+d:''); });
    });
  }
  function choose(value) {
    choice=value;
    try { localStorage.setItem(key,JSON.stringify({value:value,at:Date.now()})); } catch (_) { /* session choice still works */ }
    panel.hidden=true;
    if (value==='accepted') { if (loaded) { window['ga-disable-'+id]=false; push('consent','update',{analytics_storage:'granted'}); lastPage=''; page(); } else load(); }
    else { window['ga-disable-'+id]=true; clearCookies(); if(loaded) location.reload(); }
  }
  var style=document.createElement('style'); style.textContent='#braid-consent{position:fixed;bottom:16px;left:16px;right:16px;max-width:620px;z-index:2147483000;background:#fff;color:#17251d;border:1px solid #bcc8bf;border-radius:12px;padding:20px;box-shadow:0 8px 32px #0003;font:15px/1.5 system-ui,sans-serif}#braid-consent[hidden]{display:none}#braid-consent p{margin:0 0 12px}#braid-consent button,#braid-consent a{font:inherit}#braid-consent button{background:#173d2b;color:#fff;border:1px solid #173d2b;padding:9px 14px;border-radius:6px;cursor:pointer;margin:0 8px 6px 0}#braid-consent a{color:#173d2b;text-decoration:underline}#braid-privacy-settings{position:fixed;bottom:8px;left:8px;z-index:2147482000;background:#fff;color:#173d2b;border:1px solid #bcc8bf;padding:5px 9px;border-radius:5px;font:12px system-ui;cursor:pointer}'; document.head.appendChild(style);
  var panel=document.createElement('section');panel.id='braid-consent';panel.setAttribute('aria-label','Analytics privacy choices');panel.hidden=choice!==null;
  panel.innerHTML='<p><strong>Your analytics choice</strong></p><p>With your permission, we use Google Analytics to understand visits and improve this site. Analytics cookies help measure engagement. We keep form entries and private workspace content out of these measurements.</p><button type="button" data-choice="accepted">Allow analytics</button><button type="button" data-choice="rejected">Decline analytics</button><a href="'+(site==='8braid'||app?'/privacy':'/privacy.html')+'">Analytics privacy notice</a>';
  panel.querySelectorAll('button').forEach(function(b){b.addEventListener('click',function(){choose(b.dataset.choice);});}); document.body.appendChild(panel);
  var settings=document.createElement('button');settings.id='braid-privacy-settings';settings.type='button';settings.textContent='Privacy choices';settings.addEventListener('click',function(){panel.hidden=false;panel.querySelector('button').focus();});
  // Public Digital Fabric pages keep this persistent control in the footer so
  // it cannot cover an action or reading content on narrow screens. Consent,
  // provider loading and the allowlisted event payloads are unchanged.
  var settingsHost = site === 'digital-fabric' && !app ? (document.querySelector('footer .wrap') || document.body) : null;
  if (settingsHost) {
    style.textContent += '#braid-privacy-settings{position:static;min-height:44px;font-size:14px;align-self:flex-start;margin:0}';
    settingsHost.appendChild(settings);
  } else {
    document.body.appendChild(settings);
  }
  window.braidAnalytics={track:send,page:page};
  // Poll the route only, never inspect application state or query strings.
  setInterval(page,500);
  setInterval(function(){ if(choice!=='accepted'||document.visibilityState!=='visible')return; elapsed+=1; if(!app&&/\/journal\/[a-z0-9-]+$/.test(path())&&elapsed>=30&&depth>=75&&!engaged){engaged=true;send('article_engaged',{article_slug:path().split('/').pop()});}},1000);
  window.addEventListener('scroll',function(){if(app||choice!=='accepted')return;var total=document.documentElement.scrollHeight-window.innerHeight;if(total<=0)return;var pct=Math.min(100,Math.round(window.scrollY/total*100));[50,75,90].forEach(function(n){if(pct>=n&&depth<n){send('scroll_depth',{percent_scrolled:n});depth=n;}});},{passive:true});
  function placement(el){return el.closest('header,nav')?'navigation':el.closest('footer')?'footer':el.closest('article')?'article':'body';}
  document.addEventListener('click',function(e){
    if(app)return;var el=e.target instanceof Element?e.target.closest('a'):null;if(!el)return;
    var raw=el.getAttribute('href')||'', where=placement(el);
    if(/^(mailto:|tel:)/.test(raw)){send('contact_click',{method:raw.indexOf('mailto:')===0?'email':'phone',cta_placement:where,lead_type:site==='sovclear'?'pilot':site==='digital-fabric'?'technical_briefing':'evaluation'});return;}
    if(el.hasAttribute('data-footnote-ref')){send('footnote_click');return;}
    try{var u=new URL(raw,location.href);if(!/^https?:$/.test(u.protocol))return;
      var destination=Object.keys(hosts).find(function(k){return hosts[k].indexOf(u.hostname)>=0;});
      if(destination&&destination!==site){send('portfolio_handoff',{destination_group:destination,cta_placement:where});return;}
      if(u.origin!==location.origin){send('source_click',{destination_group:u.hostname==='github.com'?'github':'external',cta_placement:where});return;}
      if(/\.(pdf|zip|csv|xlsx)$/i.test(u.pathname)){send('file_download',{destination_group:'public_resource',cta_placement:where});return;}
      var label=el.dataset.analyticsCta || (u.hash?u.hash.slice(1):u.pathname.replace(/^\//,'')||'home');
      send('cta_click',{cta_name:label,cta_placement:where});
    }catch(_){}
  });
  document.addEventListener('toggle',function(e){if(app||!(e.target instanceof HTMLDetailsElement)||!e.target.open)return;var ds=Array.from(document.querySelectorAll('details'));send(e.target.closest('.faq-list')?'faq_open':'example_open',{section_name:'item_'+(ds.indexOf(e.target)+1)});},true);
  var observer;
  function observeSections(){if(app||!('IntersectionObserver'in window))return;if(observer)observer.disconnect();observer=new IntersectionObserver(function(entries){entries.forEach(function(entry){if(entry.isIntersecting&&choice==='accepted'){send('section_view',{section_name:entry.target.id});observer.unobserve(entry.target);}});},{threshold:0.35});document.querySelectorAll('main section[id]').forEach(function(el){observer.observe(el);});}
  load();
})();
