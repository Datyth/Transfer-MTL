# Train examples for detailed-type review

Seed 0 reservoir samples, at most 5 per pilot detailed type. Suffix meanings are not interpreted. Counts and observations refer to train.

## exist (exist)

Observation: 5564 train questions; yes=5564, no=0; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 19669838

Question: Are any plates observable in the scene?
Answer: yes

```text
0: select | plate (1191260) | deps=[]
1: exist | ? | deps=[0]
```

### Question 06673346

Question: Are there balls in this picture?
Answer: yes

```text
0: select | ball (2387613) | deps=[]
1: exist | ? | deps=[0]
```

### Question 04674403

Question: Are there chairs in the picture?
Answer: yes

```text
0: select | chair (1129708) | deps=[]
1: exist | ? | deps=[0]
```

### Question 09635740

Question: Do you see umbrellas?
Answer: yes

```text
0: select | umbrella (4204739) | deps=[]
1: exist | ? | deps=[0]
```

### Question 14394345

Question: Do you see any phones?
Answer: yes

```text
0: select | phone (2676619) | deps=[]
1: exist | ? | deps=[0]
```

## existAnd (logic)

Observation: 10683 train questions; yes=10683, no=0; 5 examples shown; sampled terminal operations=['and']. The suffix alone is not assigned a meaning.

### Question 03974833

Question: Are there both a door and a window in the picture?
Answer: yes

```text
0: select | door (1896819) | deps=[]
1: exist | ? | deps=[0]
2: select | windows (3521474)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 16400272

Question: Are there both donuts and boxes in the picture?
Answer: yes

```text
0: select | donut (3329816) | deps=[]
1: exist | ? | deps=[0]
2: select | box (1676151)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 05284374

Question: Are there both a door and a window in the picture?
Answer: yes

```text
0: select | windows (1795093) | deps=[]
1: exist | ? | deps=[0]
2: select | door (2135624)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 17954108

Question: Are there both windows and doors in the picture?
Answer: yes

```text
0: select | window (4545752) | deps=[]
1: exist | ? | deps=[0]
2: select | door (4545738)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 02160514

Question: Are there both a doll and a balloon in the image?
Answer: yes

```text
0: select | balloon (1919830) | deps=[]
1: exist | ? | deps=[0]
2: select | doll (3744143)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

## existAndC (logic)

Observation: 10753 train questions; yes=0, no=10753; 5 examples shown; sampled terminal operations=['and']. The suffix alone is not assigned a meaning.

### Question 16479600

Question: Are there both windows and cars in this scene?
Answer: no

```text
0: select | window (1626667) | deps=[]
1: exist | ? | deps=[0]
2: select | car (-)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 1041129

Question: Are there both a desk and a chair in the image?
Answer: no

```text
0: select | chair (457047) | deps=[]
1: exist | ? | deps=[0]
2: select | desk (-)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 16865807

Question: Are there both goats and giraffes in this scene?
Answer: no

```text
0: select | giraffes (350264) | deps=[]
1: exist | ? | deps=[0]
2: select | goat (-)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 0568113

Question: Are there both zebras and flamingoes in the image?
Answer: no

```text
0: select | zebra (3386709) | deps=[]
1: exist | ? | deps=[0]
2: select | flamingo (-)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 13823553

Question: Are there both bowls and dishwashers?
Answer: no

```text
0: select | dishwasher (1162801) | deps=[]
1: exist | ? | deps=[0]
2: select | bowl (-)  | deps=[]
3: exist | ? | deps=[2]
4: and |  | deps=[1, 3]
```

## existAttr (exist)

Observation: 1410 train questions; yes=1410, no=0; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 151048687

Question: Are there any airplanes that are green in the picture?
Answer: yes

```text
0: select | airplane (1941196) | deps=[]
1: filter color | green | deps=[0]
2: exist | ? | deps=[1]
```

### Question 1957470

Question: Is there a wet train in the photo?
Answer: yes

```text
0: select | train (552212) | deps=[]
1: filter | wet | deps=[0]
2: exist | ? | deps=[1]
```

### Question 161071973

Question: Is there a yellow crown in the picture?
Answer: yes

```text
0: select | crown (576951) | deps=[]
1: filter color | yellow | deps=[0]
2: exist | ? | deps=[1]
```

### Question 05816199

Question: Are there any closed laptops in this image?
Answer: yes

```text
0: select | laptops (711629) | deps=[]
1: filter | closed | deps=[0]
2: exist | ? | deps=[1]
```

### Question 0234581

Question: Are there any windows that are closed in the image?
Answer: yes

```text
0: select | window (2537184) | deps=[]
1: filter | closed | deps=[0]
2: exist | ? | deps=[1]
```

## existAttrC (exist)

Observation: 1418 train questions; yes=0, no=1418; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 07701579

Question: Do you see bags there that are yellow?
Answer: no

```text
0: select | bag (2551631) | deps=[]
1: filter color | yellow | deps=[0]
2: exist | ? | deps=[1]
```

### Question 01240976

Question: Do you see any helmets that are green?
Answer: no

```text
0: select | helmet (2429870) | deps=[]
1: filter color | green | deps=[0]
2: exist | ? | deps=[1]
```

### Question 1483633

Question: Is there a brunette woman in the photo?
Answer: no

```text
0: select | woman (553795) | deps=[]
1: filter color | brunette | deps=[0]
2: exist | ? | deps=[1]
```

### Question 0175362

Question: Is there any grass that is tall in this photo?
Answer: no

```text
0: select | grass (398433) | deps=[]
1: filter height | tall | deps=[0]
2: exist | ? | deps=[1]
```

### Question 0645891

Question: Are there any gold breads in the photo?
Answer: no

```text
0: select | bread (2101338) | deps=[]
1: filter color | gold | deps=[0]
2: exist | ? | deps=[1]
```

## existAttrNot (exist)

Observation: 1513 train questions; yes=1513, no=0; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 01585916

Question: Do you see televisions that are not black?
Answer: yes

```text
0: select | television (415101) | deps=[]
1: filter color | not(black) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 10522439

Question: Are there buses that are not green?
Answer: yes

```text
0: select | bus (2638907) | deps=[]
1: filter color | not(green) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 08305142

Question: Do you see any strawberries there that are not unripe?
Answer: yes

```text
0: select | strawberry (381144) | deps=[]
1: filter | not(unripe) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 1923632

Question: Is there any grass in the image that is not tall?
Answer: yes

```text
0: select | grass (1203911) | deps=[]
1: filter height | not(tall) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 01172068

Question: Is there any traffic light in this photograph that is not short?
Answer: yes

```text
0: select | traffic light (2225586) | deps=[]
1: filter | not(short) | deps=[0]
2: exist | ? | deps=[1]
```

## existAttrNotC (exist)

Observation: 1440 train questions; yes=0, no=1440; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 06575543

Question: Is there a soccer ball that is not pink?
Answer: no

```text
0: select | soccer ball (506155) | deps=[]
1: filter color | not(pink) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 19235067

Question: Do you see any carrot there that is not orange?
Answer: no

```text
0: select | carrot (763193) | deps=[]
1: filter color | not(orange) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 15809409

Question: Is there a tie in the photo that is not black?
Answer: no

```text
0: select | tie (514098) | deps=[]
1: filter color | not(black) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 17607979

Question: Are there any goggles in this picture that are not blue?
Answer: no

```text
0: select | goggles (655757) | deps=[]
1: filter color | not(blue) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 061018698

Question: Is there an airplane in this picture that is not gray?
Answer: no

```text
0: select | airplane (222392) | deps=[]
1: filter color | not(gray) | deps=[0]
2: exist | ? | deps=[1]
```

## existAttrOr (logic)

Observation: 8378 train questions; yes=8378, no=0; 5 examples shown; sampled terminal operations=['or']. The suffix alone is not assigned a meaning.

### Question 07405789

Question: Is there any dark mud or sand?
Answer: yes

```text
0: select | sand (2003597) | deps=[]
1: filter color | dark | deps=[0]
2: exist | ? | deps=[1]
3: select | mud (-)  | deps=[]
4: filter | dark | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 06801918

Question: Are there square clocks or mirrors?
Answer: yes

```text
0: select | mirror (233780) | deps=[]
1: filter shape | square | deps=[0]
2: exist | ? | deps=[1]
3: select | clock (233784)  | deps=[]
4: filter shape | square | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 03410325

Question: Are there either small windows or doors in this photo?
Answer: yes

```text
0: select | door (557408) | deps=[]
1: filter size | small | deps=[0]
2: exist | ? | deps=[1]
3: select | window (557415)  | deps=[]
4: filter size | small | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 05889167

Question: Do you see long trains or bridges?
Answer: yes

```text
0: select | bridge (240051) | deps=[]
1: filter length | long | deps=[0]
2: exist | ? | deps=[1]
3: select | train (240050)  | deps=[]
4: filter length | long | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 03551611

Question: Do you see either white shelves or desks?
Answer: yes

```text
0: select | desk (4318239) | deps=[]
1: filter color | white | deps=[0]
2: exist | ? | deps=[1]
3: select | shelf (-)  | deps=[]
4: filter color | white | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

## existAttrOrC (logic)

Observation: 7958 train questions; yes=0, no=7958; 5 examples shown; sampled terminal operations=['or']. The suffix alone is not assigned a meaning.

### Question 16211179

Question: Is there a white Wii controller or computer mouse?
Answer: no

```text
0: select | computer mouse (330996) | deps=[]
1: filter color | white | deps=[0]
2: exist | ? | deps=[1]
3: select | wii controllers (-)  | deps=[]
4: filter color | white | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 05913387

Question: Are there any yellow frisbees or balls?
Answer: no

```text
0: select | ball (4344240) | deps=[]
1: filter color | yellow | deps=[0]
2: exist | ? | deps=[1]
3: select | frisbee (-)  | deps=[]
4: filter color | yellow | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 12648746

Question: Are there black computer mice or headphones?
Answer: no

```text
0: select | computer mouse (232126) | deps=[]
1: filter color | black | deps=[0]
2: exist | ? | deps=[1]
3: select | headphones (-)  | deps=[]
4: filter color | black | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 07202925

Question: Are there either white tables or beds?
Answer: no

```text
0: select | table (585034) | deps=[]
1: filter color | white | deps=[0]
2: exist | ? | deps=[1]
3: select | bed (-)  | deps=[]
4: filter color | white | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 0827415

Question: Is there either any dark train or truck?
Answer: no

```text
0: select | truck (679022) | deps=[]
1: filter | dark | deps=[0]
2: exist | ? | deps=[1]
3: select | train (-)  | deps=[]
4: filter | dark | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

## existC (exist)

Observation: 5721 train questions; yes=0, no=5721; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 08903977

Question: Are there surfers in this photograph?
Answer: no

```text
0: select | surfer (-) | deps=[]
1: exist | ? | deps=[0]
```

### Question 18445495

Question: Are there any coffee makers?
Answer: no

```text
0: select | coffee maker (-) | deps=[]
1: exist | ? | deps=[0]
```

### Question 17389197

Question: Is there a laptop?
Answer: no

```text
0: select | laptop (-) | deps=[]
1: exist | ? | deps=[0]
```

### Question 16959729

Question: Are there any toothbrushes?
Answer: no

```text
0: select | toothbrush (-) | deps=[]
1: exist | ? | deps=[0]
```

### Question 08894251

Question: Is there any meat?
Answer: no

```text
0: select | meat (-) | deps=[]
1: exist | ? | deps=[0]
```

## existMaterial (exist)

Observation: 179 train questions; yes=179, no=0; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 19373375

Question: Is there a metal bench?
Answer: yes

```text
0: select | bench (996167) | deps=[]
1: filter material | metal | deps=[0]
2: exist | ? | deps=[1]
```

### Question 161073524

Question: Are there any fences that are made of metal?
Answer: yes

```text
0: select | fence (2092545) | deps=[]
1: filter material | metal | deps=[0]
2: exist | ? | deps=[1]
```

### Question 18785379

Question: Are there any plastic bottles in the picture?
Answer: yes

```text
0: select | bottle (1620283) | deps=[]
1: filter material | plastic | deps=[0]
2: exist | ? | deps=[1]
```

### Question 13256490

Question: Is there a leather couch?
Answer: yes

```text
0: select | couch (665871) | deps=[]
1: filter material | leather | deps=[0]
2: exist | ? | deps=[1]
```

### Question 13523239

Question: Are there any wood tables in this picture?
Answer: yes

```text
0: select | table (1646702) | deps=[]
1: filter material | wood | deps=[0]
2: exist | ? | deps=[1]
```

## existMaterialC (exist)

Observation: 165 train questions; yes=0, no=165; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 12602751

Question: Are there any fences that are made of wood?
Answer: no

```text
0: select | fence (3448953) | deps=[]
1: filter material | wood | deps=[0]
2: exist | ? | deps=[1]
```

### Question 121040413

Question: Is there a fence that is made of brick?
Answer: no

```text
0: select | fence (361172) | deps=[]
1: filter material | brick | deps=[0]
2: exist | ? | deps=[1]
```

### Question 1020208

Question: Is there a wood knife in the picture?
Answer: no

```text
0: select | knife (1355063) | deps=[]
1: filter material | wood | deps=[0]
2: exist | ? | deps=[1]
```

### Question 07971062

Question: Do you see any concrete bench?
Answer: no

```text
0: select | bench (510861) | deps=[]
1: filter material | concrete | deps=[0]
2: exist | ? | deps=[1]
```

### Question 15615054

Question: Is there any fence that is made of stone?
Answer: no

```text
0: select | fence (4457583) | deps=[]
1: filter material | stone | deps=[0]
2: exist | ? | deps=[1]
```

## existMaterialNot (exist)

Observation: 210 train questions; yes=210, no=0; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 111000525

Question: Are there doors that are not made of metal?
Answer: yes

```text
0: select | doors (287276) | deps=[]
1: filter material | not(metal) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 12941027

Question: Are there any knives that are not made out of stainless steel?
Answer: yes

```text
0: select | knife (832124) | deps=[]
1: filter material | not(stainless steel) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 03559693

Question: Do you see a bottle that is not made of plastic?
Answer: yes

```text
0: select | bottle (921736) | deps=[]
1: filter material | not(plastic) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 14395305

Question: Are there spatulas that are not made of wood?
Answer: yes

```text
0: select | spatula (875101) | deps=[]
1: filter material | not(wood) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 14274014

Question: Do you see a bench that is not made of concrete?
Answer: yes

```text
0: select | bench (240650) | deps=[]
1: filter material | not(concrete) | deps=[0]
2: exist | ? | deps=[1]
```

## existMaterialNotC (exist)

Observation: 189 train questions; yes=0, no=189; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 04520759

Question: Are there any skyscrapers that are not made of brick?
Answer: no

```text
0: select | skyscraper (1173599) | deps=[]
1: filter material | not(brick) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 07438827

Question: Is there a fence in this photo that is not made of brick?
Answer: no

```text
0: select | fence (3925756) | deps=[]
1: filter material | not(brick) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 10633695

Question: Is there any dog that is not made of cement?
Answer: no

```text
0: select | dog (3857132) | deps=[]
1: filter material | not(concrete) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 19932350

Question: Is there any fence that is not made of wood?
Answer: no

```text
0: select | fence (944133) | deps=[]
1: filter material | not(wood) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 181003303

Question: Are there any doors that are not made of wood?
Answer: no

```text
0: select | door (1185990) | deps=[]
1: filter material | not(wood) | deps=[0]
2: exist | ? | deps=[1]
```

## existOr (logic)

Observation: 21405 train questions; yes=21405, no=0; 5 examples shown; sampled terminal operations=['or']. The suffix alone is not assigned a meaning.

### Question 11479133

Question: Are there helmets or candles?
Answer: yes

```text
0: select | helmet (4598201) | deps=[]
1: exist | ? | deps=[0]
2: select | candle (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

### Question 041033449

Question: Are there any beds or lamps?
Answer: yes

```text
0: select | bed (3246043) | deps=[]
1: exist | ? | deps=[0]
2: select | lamp (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

### Question 00846512

Question: Are there any flags or cars in the picture?
Answer: yes

```text
0: select | flag (622084) | deps=[]
1: exist | ? | deps=[0]
2: select | car (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

### Question 14211999

Question: Do you see clocks or chandeliers?
Answer: yes

```text
0: select | clock (2062991) | deps=[]
1: exist | ? | deps=[0]
2: select | chandelier (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

### Question 112121

Question: Are there helmets or scooters in the image?
Answer: yes

```text
0: select | scooter (3394854) | deps=[]
1: exist | ? | deps=[0]
2: select | helmets (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

## existOrC (logic)

Observation: 21511 train questions; yes=0, no=21511; 5 examples shown; sampled terminal operations=['or']. The suffix alone is not assigned a meaning.

### Question 11979582

Question: Are there batteries or scrub brushes?
Answer: no

```text
0: select | batteries (-) | deps=[]
1: exist | ? | deps=[0]
2: select | scrub brush (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

### Question 03923552

Question: Are there any tissue papers or trash cans in the image?
Answer: no

```text
0: select | trash can (-) | deps=[]
1: exist | ? | deps=[0]
2: select | tissues (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

### Question 01243433

Question: Are there flags or tools in the photograph?
Answer: no

```text
0: select | tools (-) | deps=[]
1: exist | ? | deps=[0]
2: select | flag (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

### Question 04312398

Question: Are there any life vests or objects in this image?
Answer: no

```text
0: select | object (-) | deps=[]
1: exist | ? | deps=[0]
2: select | life jackets (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

### Question 16741353

Question: Are there any spectators or shoppers in the photograph?
Answer: no

```text
0: select | spectator (-) | deps=[]
1: exist | ? | deps=[0]
2: select | shopper (-)  | deps=[]
3: exist | ? | deps=[2]
4: or |  | deps=[1, 3]
```

## existRelS (exist)

Observation: 26711 train questions; yes=26711, no=0; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 0261147

Question: Are there any bar stools to the left of the food in the bowl?
Answer: yes

```text
0: select | bowl (2476973) | deps=[]
1: relate | food,in,s (3588146) | deps=[0]
2: relate | bar stool,to the left of,s (3588157) | deps=[1]
3: exist | ? | deps=[2]
```

### Question 151053395

Question: Is there any broccoli to the left of the beef that is to the left of the corn?
Answer: yes

```text
0: select | corn (2083754) | deps=[]
1: relate | beef,to the left of,s (3784127) | deps=[0]
2: relate | broccoli,to the left of,s (1939748) | deps=[1]
3: exist | ? | deps=[2]
```

### Question 19617158

Question: Is there a cabinet by the small animal?
Answer: yes

```text
0: select | animal (224906) | deps=[]
1: filter size | small | deps=[0]
2: relate | cabinets,by,s (224917) | deps=[1]
3: exist | ? | deps=[2]
```

### Question 10740271

Question: Are there chefs to the right of the man that wears a hat?
Answer: yes

```text
0: select | hat (1224541) | deps=[]
1: relate | man,wearing,s (1224540) | deps=[0]
2: relate | chef,to the right of,s (1224567) | deps=[1]
3: exist | ? | deps=[2]
```

### Question 10897605

Question: Are there men to the left of the camera on the table?
Answer: yes

```text
0: select | table (4029185) | deps=[]
1: relate | camera,on,s (4029196) | deps=[0]
2: relate | man,to the left of,s (4029213) | deps=[1]
3: exist | ? | deps=[2]
```

## existRelSC (exist)

Observation: 19663 train questions; yes=0, no=19663; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 07850118

Question: Are there monitors on the desk?
Answer: no

```text
0: select | desk (680464) | deps=[]
1: relate | monitor,on,s (-) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 15352105

Question: Are there any books to the left of the animal which is to the left of the cake?
Answer: no

```text
0: select | cake (2807237) | deps=[]
1: relate | animal,to the left of,s (3459091) | deps=[0]
2: relate | book,to the left of,s (-) | deps=[1]
3: exist | ? | deps=[2]
```

### Question 15678018

Question: Do you see a bench to the left of the people that are wearing a sweater?
Answer: no

```text
0: select | sweater (3723471) | deps=[]
1: relate | people,wearing,s (3176854) | deps=[0]
2: relate | bench,to the left of,s (-) | deps=[1]
3: exist | ? | deps=[2]
```

### Question 05625708

Question: Is there any sheep in the pen?
Answer: no

```text
0: select | pen (3638356) | deps=[]
1: relate | sheep,in,s (-) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 1188844

Question: Are there ropes on the blue boat?
Answer: no

```text
0: select | boat (322389) | deps=[]
1: filter color | blue | deps=[0]
2: relate | rope,on,s (-) | deps=[1]
3: exist | ? | deps=[2]
```

## existRelSRC (exist)

Observation: 7448 train questions; yes=0, no=7448; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 18897556

Question: Do you see a carrot to the right of the meat in the center?
Answer: no

```text
0: select | meat (2041104) | deps=[]
1: filter vposition | middle | deps=[0]
2: relate | carrot,to the right of,s (2462438) | deps=[1]
3: exist | ? | deps=[2]
```

### Question 00966125

Question: Do you see any people to the right of the fence?
Answer: no

```text
0: select | fence (675800) | deps=[]
1: relate | person,to the right of,s (675805) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 07288433

Question: Are there any women to the right of the girl on the right?
Answer: no

```text
0: select | girl (1665023) | deps=[]
1: filter hposition | right | deps=[0]
2: relate | woman,to the right of,s (2251556) | deps=[1]
3: exist | ? | deps=[2]
```

### Question 10747598

Question: Do you see people to the left of the backpack?
Answer: no

```text
0: select | backpack (2226302) | deps=[]
1: relate | person,to the left of,s (3862021) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 13571883

Question: Are there men to the left of the girl in the middle of the picture?
Answer: no

```text
0: select | girl (3120841) | deps=[]
1: filter vposition | middle | deps=[0]
2: relate | man,to the left of,s (2728192) | deps=[1]
3: exist | ? | deps=[2]
```

## existThat (exist)

Observation: 1482 train questions; yes=1482, no=0; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 08856039

Question: Is there a bus in the picture that is red?
Answer: yes

```text
0: select | bus (4672377) | deps=[]
1: filter color | red | deps=[0]
2: exist | ? | deps=[1]
```

### Question 05477558

Question: Do you see a skateboard that is blue?
Answer: yes

```text
0: select | skateboard (367958) | deps=[]
1: filter color | blue | deps=[0]
2: exist | ? | deps=[1]
```

### Question 131009456

Question: Is there a keyboard that is green?
Answer: yes

```text
0: select | keyboard (2131161) | deps=[]
1: filter color | green | deps=[0]
2: exist | ? | deps=[1]
```

### Question 03936050

Question: Is there any skateboard that is white?
Answer: yes

```text
0: select | skateboard (974845) | deps=[]
1: filter color | white | deps=[0]
2: exist | ? | deps=[1]
```

### Question 19263073

Question: Is there a hat that is black?
Answer: yes

```text
0: select | hat (1786402) | deps=[]
1: filter color | black | deps=[0]
2: exist | ? | deps=[1]
```

## existThatC (exist)

Observation: 1440 train questions; yes=0, no=1440; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 06563150

Question: Is there a bridge that is white?
Answer: no

```text
0: select | bridge (1270170) | deps=[]
1: filter color | white | deps=[0]
2: exist | ? | deps=[1]
```

### Question 04123562

Question: Is there any grass in this picture that is short?
Answer: no

```text
0: select | grass (3988402) | deps=[]
1: filter | short | deps=[0]
2: exist | ? | deps=[1]
```

### Question 10188028

Question: Is there a fence in this image that is black?
Answer: no

```text
0: select | fence (3068518) | deps=[]
1: filter color | black | deps=[0]
2: exist | ? | deps=[1]
```

### Question 11325447

Question: Do you see any bags that are white?
Answer: no

```text
0: select | bag (1745230) | deps=[]
1: filter color | white | deps=[0]
2: exist | ? | deps=[1]
```

### Question 18570777

Question: Are there any towels in the image that are purple?
Answer: no

```text
0: select | towel (2634247) | deps=[]
1: filter color | purple | deps=[0]
2: exist | ? | deps=[1]
```

## existThatNot (exist)

Observation: 128 train questions; yes=128, no=0; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 07213979

Question: Do you see any lamps there that are not off?
Answer: yes

```text
0: select | lamp (726682) | deps=[]
1: filter | not(off) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 19408589

Question: Do you see women that are not walking?
Answer: yes

```text
0: select | woman (779528) | deps=[]
1: filter pose | not(walking) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 10756009

Question: Is there a bird in the image that is not resting?
Answer: yes

```text
0: select | bird (484559) | deps=[]
1: filter activity | not(resting) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 11563145

Question: Is there a horse in this picture that is not walking?
Answer: yes

```text
0: select | horse (4418808) | deps=[]
1: filter pose | not(walking) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 09685390

Question: Do you see any children that are not standing?
Answer: yes

```text
0: select | child (1296991) | deps=[]
1: filter pose | not(standing) | deps=[0]
2: exist | ? | deps=[1]
```

## existThatNotC (exist)

Observation: 145 train questions; yes=0, no=145; 5 examples shown; sampled terminal operations=['exist']. The suffix alone is not assigned a meaning.

### Question 02414347

Question: Is there any woman that is not staring?
Answer: no

```text
0: select | woman (1213089) | deps=[]
1: filter activity | not(staring) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 19494442

Question: Is there a dog that is not running?
Answer: no

```text
0: select | dog (680793) | deps=[]
1: filter pose | not(running) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 05118538

Question: Are there any women in the photo that are not eating?
Answer: no

```text
0: select | woman (991867) | deps=[]
1: filter activity | not(eating) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 05962457

Question: Do you see a lamp in the image that is not off?
Answer: no

```text
0: select | lamp (740678) | deps=[]
1: filter | not(off) | deps=[0]
2: exist | ? | deps=[1]
```

### Question 01351646

Question: Is there any child that is not sitting?
Answer: no

```text
0: select | child (1147404) | deps=[]
1: filter pose | not(sitting) | deps=[0]
2: exist | ? | deps=[1]
```

## existThatOr (logic)

Observation: 4254 train questions; yes=4254, no=0; 5 examples shown; sampled terminal operations=['or']. The suffix alone is not assigned a meaning.

### Question 15138161

Question: Are there any tables or chairs that are dark brown?
Answer: yes

```text
0: select | chair (1016873) | deps=[]
1: filter color | dark brown | deps=[0]
2: exist | ? | deps=[1]
3: select | table (1016877)  | deps=[]
4: filter color | dark brown | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 03173854

Question: Are there frisbees or umbrellas that are blue?
Answer: yes

```text
0: select | frisbee (742013) | deps=[]
1: filter color | blue | deps=[0]
2: exist | ? | deps=[1]
3: select | umbrella (-)  | deps=[]
4: filter color | blue | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 12496134

Question: Are there any pots or fences that are silver?
Answer: yes

```text
0: select | fence (1856309) | deps=[]
1: filter color | silver | deps=[0]
2: exist | ? | deps=[1]
3: select | pot (-)  | deps=[]
4: filter color | silver | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 05254563

Question: Do you see any goggles or skis that are pink?
Answer: yes

```text
0: select | goggles (410016) | deps=[]
1: filter color | pink | deps=[0]
2: exist | ? | deps=[1]
3: select | ski (410013)  | deps=[]
4: filter color | pink | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 192149

Question: Are there any horses or dogs that are white?
Answer: yes

```text
0: select | dog (283324) | deps=[]
1: filter color | white | deps=[0]
2: exist | ? | deps=[1]
3: select | horse (-)  | deps=[]
4: filter color | white | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

## existThatOrC (logic)

Observation: 4045 train questions; yes=0, no=4045; 5 examples shown; sampled terminal operations=['or']. The suffix alone is not assigned a meaning.

### Question 10567768

Question: Is there either a doll or a teddy bear that is not sitting?
Answer: no

```text
0: select | teddy bear (513022) | deps=[]
1: filter pose | not(sitting) | deps=[0]
2: exist | ? | deps=[1]
3: select | doll (-)  | deps=[]
4: filter pose | not(sitting) | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 08457427

Question: Is there either a window or a door that is made of metal?
Answer: no

```text
0: select | door (397007) | deps=[]
1: filter material | metal | deps=[0]
2: exist | ? | deps=[1]
3: select | window (-)  | deps=[]
4: filter material | metal | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 1395155

Question: Are there either any pots or pans that are not made of glass?
Answer: no

```text
0: select | pot (2610115) | deps=[]
1: filter material | not(glass) | deps=[0]
2: exist | ? | deps=[1]
3: select | pan (-)  | deps=[]
4: filter material | not(glass) | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 04708477

Question: Is there a plate or a bottle that is not pink?
Answer: no

```text
0: select | plate (274843) | deps=[]
1: filter color | not(pink) | deps=[0]
2: exist | ? | deps=[1]
3: select | bottle (-)  | deps=[]
4: filter color | not(pink) | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

### Question 05635685

Question: Are there computer mice or Wii controllers that are not white?
Answer: no

```text
0: select | computer mouse (2292024) | deps=[]
1: filter color | not(white) | deps=[0]
2: exist | ? | deps=[1]
3: select | wii controller (-)  | deps=[]
4: filter color | not(white) | deps=[3]
5: exist | ? | deps=[4]
6: or |  | deps=[2, 5]
```

## relVerify (verifyRel)

Observation: 27777 train questions; yes=27777, no=0; 5 examples shown; sampled terminal operations=['verify rel']. The suffix alone is not assigned a meaning.

### Question 10301740

Question: Is the person on the boat holding the umbrella that is on the right of the photo?
Answer: yes

```text
0: select | boat (1327258) | deps=[]
1: relate | person,on,s (1327262) | deps=[0]
2: verify rel | umbrella,holding,o (1327260) | deps=[1]
```

### Question 13156439

Question: Is the person in the cart wearing a helmet?
Answer: yes

```text
0: select | cart (645613) | deps=[]
1: relate | person,in,s (645627) | deps=[0]
2: verify rel | helmet,wearing,o (645626) | deps=[1]
```

### Question 021070822

Question: Is the sky behind the sign that is red and white?
Answer: yes

```text
0: select | sky (1130146) | deps=[]
1: verify rel | stop sign,behind,o (1130129) | deps=[0]
```

### Question 05447083

Question: Is the dog to the right of the screen on the left side?
Answer: yes

```text
0: select | dog (2432197) | deps=[]
1: verify rel | screen,to the right of,o (2027469) | deps=[0]
```

### Question 03153081

Question: Is the white table under the plate?
Answer: yes

```text
0: select | table (1144175) | deps=[]
1: filter color | white | deps=[0]
2: verify rel | plate,under,o (1144174) | deps=[1]
```

## relVerifyCo (verifyRel)

Observation: 21726 train questions; yes=0, no=21726; 5 examples shown; sampled terminal operations=['verify rel']. The suffix alone is not assigned a meaning.

### Question 17779696

Question: Is she using a laptop?
Answer: no

```text
0: select | she (940728) | deps=[]
1: verify rel | laptop,using,o (-) | deps=[0]
```

### Question 10124001

Question: Does the woman wear a skirt?
Answer: no

```text
0: select | woman (577835) | deps=[]
1: verify rel | skirt,wearing,o (-) | deps=[0]
```

### Question 12985736

Question: Is that food to the right of antelopes?
Answer: no

```text
0: select | food (292985) | deps=[]
1: verify rel | antelopes,to the right of,o (-) | deps=[0]
```

### Question 12549209

Question: Is that man to the left of a backpack?
Answer: no

```text
0: select | man (4162865) | deps=[]
1: verify rel | backpack,to the left of,o (-) | deps=[0]
```

### Question 14198072

Question: Is the corn on a can?
Answer: no

```text
0: select | corn (3847677) | deps=[]
1: verify rel | can,on,o (-) | deps=[0]
```

## relVerifyCop (verifyRel)

Observation: 35 train questions; yes=0, no=35; 5 examples shown; sampled terminal operations=['verify rel']. The suffix alone is not assigned a meaning.

### Question 17345909

Question: Is the bike behind the man?
Answer: no

```text
0: select | man (160087) | deps=[]
1: verify rel | bike,behind,s (160088) | deps=[0]
```

### Question 11600573

Question: Is the man behind the bike?
Answer: no

```text
0: select | bike (362779) | deps=[]
1: verify rel | man,behind,s (362783) | deps=[0]
```

### Question 05388635

Question: Is the sign above the window?
Answer: no

```text
0: select | window (273360) | deps=[]
1: verify rel | sign,above,s (650579) | deps=[0]
```

### Question 04670335

Question: Is the window above the sign?
Answer: no

```text
0: select | sign (262635) | deps=[]
1: verify rel | window,above,s (262611) | deps=[0]
```

### Question 10490435

Question: Is the window above the sign?
Answer: no

```text
0: select | sign (1545536) | deps=[]
1: verify rel | window,above,s (1545537) | deps=[0]
```

## relVerifyCr (verifyRel)

Observation: 6985 train questions; yes=0, no=6985; 5 examples shown; sampled terminal operations=['verify rel']. The suffix alone is not assigned a meaning.

### Question 02742385

Question: Is the white truck to the left of the man that is wearing a shirt?
Answer: no

```text
0: select | shirt (1130691) | deps=[]
1: relate | man,wearing,s (1130692) | deps=[0]
2: verify rel | truck,to the left of,s (1130687) | deps=[1]
```

### Question 15968480

Question: Is the car to the left of the box behind the pole?
Answer: no

```text
0: select | pole (4314151) | deps=[]
1: relate | box,behind,s (4529641) | deps=[0]
2: verify rel | car,to the left of,s (4314157) | deps=[1]
```

### Question 03643798

Question: Is the cup to the left of the food on the plate?
Answer: no

```text
0: select | plate (3111272) | deps=[]
1: relate | food,on,s (3542960) | deps=[0]
2: verify rel | cup,to the left of,s (3085042) | deps=[1]
```

### Question 12282583

Question: Is the curtain to the right of a television?
Answer: no

```text
0: select | television (1792245) | deps=[]
1: verify rel | curtain,to the right of,s (2281561) | deps=[0]
```

### Question 19278034

Question: Is the wood shelf to the right of a cabinet?
Answer: no

```text
0: select | cabinet (2867431) | deps=[]
1: verify rel | shelf,to the right of,s (3471911) | deps=[0]
```

## twoDifferent (compare)

Observation: 4476 train questions; yes=4476, no=0; 5 examples shown; sampled terminal operations=['different color']. The suffix alone is not assigned a meaning.

### Question 12519885

Question: Is the book different in color than the logo?
Answer: yes

```text
0: select | logo (758137) | deps=[]
1: select | book (758126)  | deps=[]
2: different color |  | deps=[0, 1]
```

### Question 19601051

Question: Does the van have a different color than the truck?
Answer: yes

```text
0: select | truck (754801) | deps=[]
1: select | van (754786)  | deps=[]
2: different color |  | deps=[0, 1]
```

### Question 17601056

Question: Do the chair and the topping have a different colors?
Answer: yes

```text
0: select | topping (2632816) | deps=[]
1: select | chair (2315236)  | deps=[]
2: different color |  | deps=[0, 1]
```

### Question 161008604

Question: Do the outfit and the fence have a different colors?
Answer: yes

```text
0: select | fence (2271596) | deps=[]
1: select | outfit (2102353)  | deps=[]
2: different color |  | deps=[0, 1]
```

### Question 14227582

Question: Do the cheese and the lettuce have a different colors?
Answer: yes

```text
0: select | lettuce (526464) | deps=[]
1: select | cheese (526460)  | deps=[]
2: different color |  | deps=[0, 1]
```

## twoDifferentC (compare)

Observation: 4361 train questions; yes=0, no=4361; 5 examples shown; sampled terminal operations=['different color']. The suffix alone is not assigned a meaning.

### Question 151057170

Question: Do the street and the shoe have a different colors?
Answer: no

```text
0: select | street (1319687) | deps=[]
1: select | shoe (3848115)  | deps=[]
2: different color |  | deps=[0, 1]
```

### Question 07604969

Question: Do the wall and the car have a different colors?
Answer: no

```text
0: select | wall (730117) | deps=[]
1: select | car (730103)  | deps=[]
2: different color |  | deps=[0, 1]
```

### Question 07409202

Question: Does the spoon of the glass have a different color than the backpack?
Answer: no

```text
0: select | spoon (734986) | deps=[]
1: select | backpack (734997)  | deps=[]
2: different color |  | deps=[0, 1]
```

### Question 0415249

Question: Does the car have a different color than the sky?
Answer: no

```text
0: select | car (885754) | deps=[]
1: select | sky (885767)  | deps=[]
2: different color |  | deps=[0, 1]
```

### Question 14250087

Question: Is the color of the saucer different than the coffee mug?
Answer: no

```text
0: select | saucer (3356081) | deps=[]
1: select | coffee mug (3146483)  | deps=[]
2: different color |  | deps=[0, 1]
```

## twoSame (compare)

Observation: 4398 train questions; yes=4398, no=0; 5 examples shown; sampled terminal operations=['same color']. The suffix alone is not assigned a meaning.

### Question 13411625

Question: Do the shirt and the tennis racket have the same color?
Answer: yes

```text
0: select | shirt (399151) | deps=[]
1: select | racket (399146)  | deps=[]
2: same color |  | deps=[0, 1]
```

### Question 12669741

Question: Do the net and the hat have the same color?
Answer: yes

```text
0: select | net (2518583) | deps=[]
1: select | hat (2627443)  | deps=[]
2: same color |  | deps=[0, 1]
```

### Question 16438148

Question: Is the backpack the same color as the pole?
Answer: yes

```text
0: select | backpack (687812) | deps=[]
1: select | pole (687822)  | deps=[]
2: same color |  | deps=[0, 1]
```

### Question 151055484

Question: Is the snowboard the same color as the helmet?
Answer: yes

```text
0: select | snowboard (337550) | deps=[]
1: select | helmet (337553)  | deps=[]
2: same color |  | deps=[0, 1]
```

### Question 0436179

Question: Is the color of the chair the same as the watch?
Answer: yes

```text
0: select | chair (3082989) | deps=[]
1: select | watch (3693234)  | deps=[]
2: same color |  | deps=[0, 1]
```

## twoSameC (compare)

Observation: 4464 train questions; yes=0, no=4464; 5 examples shown; sampled terminal operations=['same color']. The suffix alone is not assigned a meaning.

### Question 03206679

Question: Is the color of the bowl the same as the candle?
Answer: no

```text
0: select | candle (3314855) | deps=[]
1: select | bowl (3341380)  | deps=[]
2: same color |  | deps=[0, 1]
```

### Question 09793492

Question: Are the backpack and the box the same color?
Answer: no

```text
0: select | box (2100946) | deps=[]
1: select | backpack (2071938)  | deps=[]
2: same color |  | deps=[0, 1]
```

### Question 03560586

Question: Do the keyboard and the curtain have the same color?
Answer: no

```text
0: select | curtain (2646953) | deps=[]
1: select | keyboard (2665502)  | deps=[]
2: same color |  | deps=[0, 1]
```

### Question 02820596

Question: Is the blouse the same color as the wall?
Answer: no

```text
0: select | blouse (980643) | deps=[]
1: select | wall (980670)  | deps=[]
2: same color |  | deps=[0, 1]
```

### Question 15593976

Question: Is the color of the shirt the same as the bed?
Answer: no

```text
0: select | shirt (671560) | deps=[]
1: select | bed (671553)  | deps=[]
2: same color |  | deps=[0, 1]
```

## twoSameMaterial (compare)

Observation: 701 train questions; yes=701, no=0; 5 examples shown; sampled terminal operations=['same material']. The suffix alone is not assigned a meaning.

### Question 04605544

Question: Are both the floor and the door made of the same material?
Answer: yes

```text
0: select | floor (912893) | deps=[]
1: select | door (912899)  | deps=[]
2: same material |  | deps=[0, 1]
```

### Question 05956189

Question: Are both the floor and the door made of the same material?
Answer: yes

```text
0: select | floor (740248) | deps=[]
1: select | door (740250)  | deps=[]
2: same material |  | deps=[0, 1]
```

### Question 01389045

Question: Is the door made of the same material as the floor?
Answer: yes

```text
0: select | door (1822276) | deps=[]
1: select | floor (2215639)  | deps=[]
2: same material |  | deps=[0, 1]
```

### Question 04768551

Question: Is the bottle made of the same material as the window?
Answer: yes

```text
0: select | bottle (396450) | deps=[]
1: select | window (396439)  | deps=[]
2: same material |  | deps=[0, 1]
```

### Question 17148089

Question: Are both the frame and the door made of the same material?
Answer: yes

```text
0: select | frame (421050) | deps=[]
1: select | door (421052)  | deps=[]
2: same material |  | deps=[0, 1]
```

## twoSameMaterialC (compare)

Observation: 1148 train questions; yes=0, no=1148; 5 examples shown; sampled terminal operations=['same material']. The suffix alone is not assigned a meaning.

### Question 101020828

Question: Are both the bear and the table made of the same material?
Answer: no

```text
0: select | bear (1158873) | deps=[]
1: select | table (1158872)  | deps=[]
2: same material |  | deps=[0, 1]
```

### Question 02300736

Question: Is the basket made of the same material as the kitchen chair?
Answer: no

```text
0: select | basket (520913) | deps=[]
1: select | chair (520891)  | deps=[]
2: same material |  | deps=[0, 1]
```

### Question 00856718

Question: Are both the container and the bowl made of the same material?
Answer: no

```text
0: select | container (214484) | deps=[]
1: select | bowl (214479)  | deps=[]
2: same material |  | deps=[0, 1]
```

### Question 08147326

Question: Are both the pole and the skateboard made of the same material?
Answer: no

```text
0: select | pole (1014490) | deps=[]
1: select | skateboard (1014488)  | deps=[]
2: same material |  | deps=[0, 1]
```

### Question 12868958

Question: Are both the toaster and the floor made of the same material?
Answer: no

```text
0: select | toaster (4051020) | deps=[]
1: select | floor (4050954)  | deps=[]
2: same material |  | deps=[0, 1]
```

## verifyAttr (verifyAttr)

Observation: 6650 train questions; yes=6650, no=0; 5 examples shown; sampled terminal operations=['verify', 'verify activity', 'verify color']. The suffix alone is not assigned a meaning.

### Question 19980927

Question: Is the mirror black?
Answer: yes

```text
0: select | mirror (409439) | deps=[]
1: verify color | black | deps=[0]
```

### Question 1198891

Question: Is the shirt long sleeved?
Answer: yes

```text
0: select | shirt (3689646) | deps=[]
1: verify | long sleeved | deps=[0]
```

### Question 14950756

Question: Is the coat blue?
Answer: yes

```text
0: select | coat (933220) | deps=[]
1: verify color | blue | deps=[0]
```

### Question 03995572

Question: Is the man posing?
Answer: yes

```text
0: select | man (392877) | deps=[]
1: verify activity | posing | deps=[0]
```

### Question 01985355

Question: Is the van red?
Answer: yes

```text
0: select | van (1349592) | deps=[]
1: verify color | red | deps=[0]
```

## verifyAttrAnd (logic)

Observation: 1219 train questions; yes=1219, no=0; 5 examples shown; sampled terminal operations=['and']. The suffix alone is not assigned a meaning.

### Question 06701037

Question: Do both the faucet near the glass and the dispenser to the left of the towel appear to be silver?
Answer: yes

```text
0: select | glass (874619) | deps=[]
1: relate | faucet,near,s (874627) | deps=[0]
2: verify color | silver | deps=[1]
3: select | towel (874616)  | deps=[]
4: relate | dispenser,to the left of,s (874622) | deps=[3]
5: verify color | silver | deps=[4]
6: and |  | deps=[2, 5]
```

### Question 18318632

Question: Are the rope and the picture both white?
Answer: yes

```text
0: select | rope (219451) | deps=[]
1: verify color | white | deps=[0]
2: select | picture (219462)  | deps=[]
3: verify color | white | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 09937919

Question: Do the pepper and the vegetable that is to the left of the olive both have green color?
Answer: yes

```text
0: select | pepper (881950) | deps=[]
1: verify color | green | deps=[0]
2: select | olive (881943)  | deps=[]
3: relate | vegetable,to the left of,s (881941) | deps=[2]
4: verify color | green | deps=[3]
5: and |  | deps=[1, 4]
```

### Question 18698183

Question: Are both the guy and the lady sitting?
Answer: yes

```text
0: select | guy (576121) | deps=[]
1: verify pose | sitting | deps=[0]
2: select | lady (576123)  | deps=[]
3: verify pose | sitting | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 07882235

Question: Are both the necktie and the small watch black?
Answer: yes

```text
0: select | tie (654392) | deps=[]
1: verify color | black | deps=[0]
2: select | watch (654405)  | deps=[]
3: filter size | small | deps=[2]
4: verify color | black | deps=[3]
5: and |  | deps=[1, 4]
```

## verifyAttrC (verifyAttr)

Observation: 6833 train questions; yes=0, no=6833; 5 examples shown; sampled terminal operations=['verify color']. The suffix alone is not assigned a meaning.

### Question 05681662

Question: Is the table white?
Answer: no

```text
0: select | table (452759) | deps=[]
1: verify color | white | deps=[0]
```

### Question 01426023

Question: Does the bowl look blue?
Answer: no

```text
0: select | bowl (3475764) | deps=[]
1: verify color | blue | deps=[0]
```

### Question 08166100

Question: Is that van orange?
Answer: no

```text
0: select | van (4553663) | deps=[]
1: verify color | orange | deps=[0]
```

### Question 09846789

Question: Is the hair brown?
Answer: no

```text
0: select | hair (4593616) | deps=[]
1: verify color | brown | deps=[0]
```

### Question 11942816

Question: Is the painting green?
Answer: no

```text
0: select | painting (662088) | deps=[]
1: verify color | green | deps=[0]
```

## verifyAttrCThis (verifyAttr)

Observation: 641 train questions; yes=0, no=641; 5 examples shown; sampled terminal operations=['verify age', 'verify color', 'verify size']. The suffix alone is not assigned a meaning.

### Question 16205297

Question: Is this an old man?
Answer: no

```text
0: select | man (1101445) | deps=[]
1: verify age | old | deps=[0]
```

### Question 08737051

Question: Is this a silver bike?
Answer: no

```text
0: select | bike (1316612) | deps=[]
1: verify color | silver | deps=[0]
```

### Question 01664759

Question: Is this a blue bus?
Answer: no

```text
0: select | bus (1296896) | deps=[]
1: verify color | blue | deps=[0]
```

### Question 02658501

Question: Is this a large horse?
Answer: no

```text
0: select | horse (723028) | deps=[]
1: verify size | large | deps=[0]
```

### Question 031043377

Question: Is this a silver laptop?
Answer: no

```text
0: select | laptop (1264417) | deps=[]
1: verify color | silver | deps=[0]
```

## verifyAttrK (verifyAttr)

Observation: 10028 train questions; yes=10028, no=0; 5 examples shown; sampled terminal operations=['verify activity', 'verify color', 'verify size']. The suffix alone is not assigned a meaning.

### Question 15362677

Question: Does the chain have gold color?
Answer: yes

```text
0: select | chain (763058) | deps=[]
1: verify color | gold | deps=[0]
```

### Question 00131583

Question: Does the bag on the motorcycle seem to be sleeping?
Answer: yes

```text
0: select | motorcycle (4566019) | deps=[]
1: relate | bag,on,s (4249722) | deps=[0]
2: verify activity | sleeping | deps=[1]
```

### Question 18985775

Question: Does the store look small?
Answer: yes

```text
0: select | store (580430) | deps=[]
1: verify size | small | deps=[0]
```

### Question 14631816

Question: Does the umbrella to the left of the other umbrella look black?
Answer: yes

```text
0: select | umbrella (962328) | deps=[]
1: relate | umbrella,to the left of,s (962329) | deps=[0]
2: verify color | black | deps=[1]
```

### Question 05856003

Question: Does the red container have large size?
Answer: yes

```text
0: select | container (3071467) | deps=[]
1: filter color | red | deps=[0]
2: verify size | large | deps=[1]
```

## verifyAttrKC (verifyAttr)

Observation: 10209 train questions; yes=0, no=10209; 5 examples shown; sampled terminal operations=['verify color', 'verify pose', 'verify size']. The suffix alone is not assigned a meaning.

### Question 02305361

Question: Does the beer mug have small size?
Answer: no

```text
0: select | beer mug (4120263) | deps=[]
1: verify size | small | deps=[0]
```

### Question 11962732

Question: Does the man to the left of the players seem to be walking?
Answer: no

```text
0: select | players (695468) | deps=[]
1: relate | man,to the left of,s (695483) | deps=[0]
2: verify pose | walking | deps=[1]
```

### Question 07950556

Question: Does the car look black?
Answer: no

```text
0: select | car (3803041) | deps=[]
1: verify color | black | deps=[0]
```

### Question 02328786

Question: Does that shirt look pink?
Answer: no

```text
0: select | shirt (366597) | deps=[]
1: verify color | pink | deps=[0]
```

### Question 05418680

Question: Does the hair that is not long look black?
Answer: no

```text
0: select | hair (156992) | deps=[]
1: filter length | not(long) | deps=[0]
2: verify color | black | deps=[1]
```

## verifyAttrThis (verifyAttr)

Observation: 618 train questions; yes=618, no=0; 5 examples shown; sampled terminal operations=['verify age', 'verify color', 'verify pattern', 'verify size']. The suffix alone is not assigned a meaning.

### Question 11627551

Question: Is that a young man?
Answer: yes

```text
0: select | man (690425) | deps=[]
1: verify age | young | deps=[0]
```

### Question 17280752

Question: Is this a large mirror?
Answer: yes

```text
0: select | mirror (1987035) | deps=[]
1: verify size | large | deps=[0]
```

### Question 161028881

Question: Is this a white truck?
Answer: yes

```text
0: select | truck (953999) | deps=[]
1: verify color | white | deps=[0]
```

### Question 12255110

Question: Is this a striped tablecloth?
Answer: yes

```text
0: select | tablecloth (674596) | deps=[]
1: verify pattern | striped | deps=[0]
```

### Question 08261468

Question: Is that a black computer mouse?
Answer: yes

```text
0: select | computer mouse (2943338) | deps=[]
1: verify color | black | deps=[0]
```

## verifyAttrs (logic)

Observation: 11742 train questions; yes=11742, no=0; 5 examples shown; sampled terminal operations=['and']. The suffix alone is not assigned a meaning.

### Question 16410932

Question: Does that dirt look dry and rocky?
Answer: yes

```text
0: select | dirt (3183921) | deps=[]
1: verify | dry | deps=[0]
2: verify | rocky  | deps=[0]
3: and |  | deps=[1, 2]
```

### Question 09869729

Question: Is the hat old and black?
Answer: yes

```text
0: select | hat (2350862) | deps=[]
1: verify color | black | deps=[0]
2: verify | old  | deps=[0]
3: and |  | deps=[1, 2]
```

### Question 00418773

Question: Is the snow white and thick?
Answer: yes

```text
0: select | snow (1172522) | deps=[]
1: verify thickness | thick | deps=[0]
2: verify color | white  | deps=[0]
3: and |  | deps=[1, 2]
```

### Question 05528420

Question: Is the airplane gray and small?
Answer: yes

```text
0: select | airplane (1215157) | deps=[]
1: verify color | gray | deps=[0]
2: verify size | small  | deps=[0]
3: and |  | deps=[1, 2]
```

### Question 19468941

Question: Is the tie striped and black?
Answer: yes

```text
0: select | tie (1188228) | deps=[]
1: verify color | black | deps=[0]
2: verify pattern | striped  | deps=[0]
3: and |  | deps=[1, 2]
```

## verifyAttrsC (logic)

Observation: 11999 train questions; yes=0, no=11999; 5 examples shown; sampled terminal operations=['and']. The suffix alone is not assigned a meaning.

### Question 04712622

Question: Is the carpet dirty and blue?
Answer: no

```text
0: select | carpet (220721) | deps=[]
1: verify color | blue | deps=[0]
2: verify cleanliness | dirty  | deps=[0]
3: and |  | deps=[1, 2]
```

### Question 12740256

Question: Is the appliance next to the wall both large and white?
Answer: no

```text
0: select | wall (1035918) | deps=[]
1: relate | appliance,next to,s (1035915) | deps=[0]
2: verify size | large | deps=[1]
3: verify color | white  | deps=[1]
4: and |  | deps=[2, 3]
```

### Question 16152587

Question: Does the vase to the left of the other vase have purple color and small size?
Answer: no

```text
0: select | vase (1067603) | deps=[]
1: relate | vase,to the left of,s (1067602) | deps=[0]
2: verify color | purple | deps=[1]
3: verify size | small  | deps=[1]
4: and |  | deps=[2, 3]
```

### Question 06771409

Question: Does the wine bottle look curved and green?
Answer: no

```text
0: select | wine bottle (763864) | deps=[]
1: verify | curved | deps=[0]
2: verify color | green  | deps=[0]
3: and |  | deps=[1, 2]
```

### Question 0255845

Question: Are the trunks wooden and fat?
Answer: no

```text
0: select | trunks (4143312) | deps=[]
1: verify fatness | fat | deps=[0]
2: verify material | wood  | deps=[0]
3: and |  | deps=[1, 2]
```

## verifyMaterialAnd (logic)

Observation: 82 train questions; yes=82, no=0; 5 examples shown; sampled terminal operations=['and']. The suffix alone is not assigned a meaning.

### Question 03847950

Question: Are both the planter and the vase made of clay?
Answer: yes

```text
0: select | planter (3901784) | deps=[]
1: verify material | clay | deps=[0]
2: select | vase (1764681)  | deps=[]
3: verify material | clay | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 05730055

Question: Are both the TV stand that looks brown and the round table made of wood?
Answer: yes

```text
0: select | tv stand (2194700) | deps=[]
1: filter color | brown | deps=[0]
2: verify material | wood | deps=[1]
3: select | table (2890044)  | deps=[]
4: filter shape | round | deps=[3]
5: verify material | wood | deps=[4]
6: and |  | deps=[2, 5]
```

### Question 03311774

Question: Are both the nightstand and the cabinet made of wood?
Answer: yes

```text
0: select | nightstand (934040) | deps=[]
1: verify material | wood | deps=[0]
2: select | cabinet (934039)  | deps=[]
3: verify material | wood | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 12172316

Question: Are both the can and the tray made of metal?
Answer: yes

```text
0: select | can (749170) | deps=[]
1: verify material | metal | deps=[0]
2: select | tray (749154)  | deps=[]
3: verify material | metal | deps=[2]
4: and |  | deps=[1, 3]
```

### Question 00704009

Question: Are both the box that is to the right of the girl and the box that is to the left of the water bottle made of cardboard?
Answer: yes

```text
0: select | girl (987495) | deps=[]
1: relate | box,to the right of,s (987502) | deps=[0]
2: verify material | cardboard | deps=[1]
3: select | water bottle (987506)  | deps=[]
4: relate | box,to the left of,s (987503) | deps=[3]
5: verify material | cardboard | deps=[4]
6: and |  | deps=[2, 5]
```

