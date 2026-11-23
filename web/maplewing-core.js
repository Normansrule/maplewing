// Maplewing physics core (MIT). Same equations as sim/phase0_compare.py.
const G=9.80665;
const rho=h=>{const T=288.15-0.0065*h;return 1.225*Math.pow(T/288.15,4.2559)};
// Real ThrustCurve.org curves (see sim/motors/motors.json). Linear interpolation; propellant
// burns in proportion to impulse delivered, exactly as sim/phase0_compare.py does.
function prepMotor(m){const c=m.curve,cum=[0];for(let i=1;i<c.length;i++)cum.push(cum[i-1]+(c[i][0]-c[i-1][0])*(c[i][1]+c[i-1][1])/2);m.cum=cum;m.I=cum[cum.length-1];m.tb=c[c.length-1][0];return m}
function seg(c,t){let lo=0,hi=c.length-1;while(hi-lo>1){const mid=(lo+hi)>>1;if(c[mid][0]<=t)lo=mid;else hi=mid}return lo}
function thrust(m,t){if(t<=0||t>=m.tb)return 0;const c=m.curve,i=seg(c,t),[t0,f0]=c[i],[t1,f1]=c[i+1];return f0+(f1-f0)*(t-t0)/(t1-t0)}
function motorMass(m,t){if(t<=0)return m.mt;if(t>=m.tb)return m.mt-m.mp;const c=m.curve,i=seg(c,t),[t0,f0]=c[i];return m.mt-m.mp*(m.cum[i]+(t-t0)*(f0+thrust(m,t))/2)/m.I}
const C6_5=prepMotor({name:'Estes C6-5',curve:[[0,0],[0.031,0.946],[0.092,4.826],[0.139,9.936],[0.192,14.09],[0.209,11.446],[0.231,7.381],[0.248,6.151],[0.292,5.489],[0.37,4.921],[0.475,4.448],[0.671,4.258],[0.702,4.542],[0.723,4.164],[0.85,4.448],[1.063,4.353],[1.211,4.353],[1.242,4.069],[1.303,4.258],[1.468,4.353],[1.656,4.448],[1.821,4.448],[1.834,2.933],[1.847,1.325],[1.86,0]],mp:0.0108,mt:0.0241});
function finsCna(N,s,cr,ct,xs,d){const lf=Math.hypot(s,xs+ct/2-cr/2);const c=(4*N*(s/d)**2)/(1+Math.sqrt(1+(2*lf/(cr+ct))**2));const r=d/2;return c*(1+r/(s+r))}
function finsXcp(xf,s,cr,ct,xs){return xf+xs*(cr+2*ct)/(3*(cr+ct))+(cr+ct-cr*ct/(cr+ct))/6}
function model(p){ // Seedling model rocket on an Estes C6-5 (ThrustCurve.org curve)
  const d=0.0248, Ln=0.10, L=p.len, dry=0.068+0.04*(L-0.55)+0.2*(p.ringD-0.055)+0.1*(p.chord-0.04)+0.03*(p.rotor-0.30), cgDry=0.32*(L/0.55);
  const mot=C6_5, mcg=L-0.05;
  const Dm=p.ringD, h=(Dm-d)/2, N=Math.PI*Dm/h, c=p.chord, xf=L-c-0.005;
  const cnN=2, xN=0.466*Ln, cnT=finsCna(N,h,c,c,0,d), xT=finsXcp(xf,h,c,c,0);
  const cp=(cnN*xN+cnT*xT)/(cnN+cnT), m0=dry+mot.mt, cg=(dry*cgDry+mot.mt*mcg)/m0;
  const margin=(cp-cg)/d;
  const cd=0.70+0.5*(Dm-0.055)+3*(c-0.04); // ASSUMED: 0.70 at the Phase 0 design, growing with ring size
  const A=Math.PI*d*d/4;
  let t=0,hh=0,v=0,dt=0.002;
  while(true){const m=dry+motorMass(mot,t);const F=thrust(mot,t);let a=(F-0.5*rho(1300+hh)*v*Math.abs(v)*cd*A)/m-G;if(hh<=0&&a<0&&t<mot.tb)a=0;v+=a*dt;hh+=v*dt;t+=dt;if(t>mot.tb&&v<=0)break;if(t>40)break}
  const md=dry+mot.mt-mot.mp, S=Math.PI*p.rotor**2/4, vd=Math.sqrt(2*md*G/(rho(1300)*1.0*S));
  return {margin,apogee:hh,vd,cp,cg,cd,mass:m0};
}


if (typeof module!=='undefined') module.exports={rho,finsCna,finsXcp,model,prepMotor,thrust,motorMass};
