var myIcons = new SVGMorpheus('#Layer_1');


function play(){
  myIcons.to('phone', {duration: 1000, easing: 'quad-in', rotation: 'none'});

  setTimeout(function(){
    myIcons.to('tablet', {duration: 1000, easing: 'quad-in', rotation: 'none'});
  }, 2000)

  setTimeout(function(){
    myIcons.to('computer', {duration: 1000, easing: 'quad-in', rotation: 'none'});
  }, 4000)
}
document.getElementById("Layer_1").onclick = function(){ play() };