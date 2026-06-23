(function(){
  var canvas = document.getElementById('bcanvas');
  var ctx = canvas.getContext('2d');
  var W, H, cx, cy;

  function resize(){
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
    cx = W/2; cy = H/2;
  }
  window.addEventListener('resize', resize);
  resize();

  var t = 0, modo = 'reposo';

  // Configuración de la presencia (después la haremos editable)
  var cfg = {
    col: '155,125,255',
    cant: 140,
    disp: 100,
    vel: 100,
    sz: 100,
    react: 100,
    core: 100,
    flat: 78
  };

  var P = [];
  function rebuild(n){
    P = [];
    for(var i=0;i<n;i++){
      P.push({
        a: Math.random()*Math.PI*2,
        r: 30 + Math.random()*95,
        s: 0.25 + Math.random()*0.9,
        sz: 0.6 + Math.random()*1.8,
        tw: Math.random()*Math.PI*2
      });
    }
  }
  rebuild(cfg.cant);

  function voz(){
    var base = (modo==='reposo')
      ? (0.12 + 0.06*Math.sin(t*0.04))
      : (0.45 + 0.55*Math.abs(Math.sin(t*0.07))*(0.55+0.45*Math.sin(t*0.21)));
    return base * (cfg.react/100);
  }

  function loop(){
    t += cfg.vel/100;
    ctx.clearRect(0,0,W,H);
    var v = voz();
    var col = cfg.col;
    var flat = cfg.flat/100;

    // núcleo
    if(cfg.core > 0){
      var coreR = (5 + v*5) * (cfg.core/100);
      var g = ctx.createRadialGradient(cx,cy,0,cx,cy,Math.max(1,coreR*4));
      g.addColorStop(0,'rgba('+col+','+(0.5+v*0.4)+')');
      g.addColorStop(1,'rgba('+col+',0)');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx,cy,Math.max(1,coreR*4),0,Math.PI*2); ctx.fill();
      ctx.beginPath(); ctx.arc(cx,cy,coreR,0,Math.PI*2);
      ctx.fillStyle = 'rgba(245,245,255,'+(0.7+v*0.3)+')'; ctx.fill();
    }

    // partículas
    for(var i=0;i<P.length;i++){
      var p = P[i];
      p.a += 0.0016*p.s*(0.5+v);
      p.tw += 0.05;
      var rr = (p.r*(cfg.disp/100)) + v*55*p.s*(cfg.disp/100);
      var x = cx + Math.cos(p.a)*rr;
      var y = cy + Math.sin(p.a)*rr*flat;
      var alpha = (0.15 + v*0.55)*(0.6+0.4*Math.sin(p.tw));
      var size = p.sz*(0.5+v*0.9)*(cfg.sz/100);
      ctx.beginPath();
      ctx.arc(x,y,Math.max(0.2,size),0,Math.PI*2);
      ctx.fillStyle = 'rgba('+col+','+alpha+')';
      ctx.fill();
    }
    requestAnimationFrame(loop);
  }
  loop();

  // Función expuesta para cambiar el estado desde Python después
  window.setEstado = function(m){ modo = m; };
})();