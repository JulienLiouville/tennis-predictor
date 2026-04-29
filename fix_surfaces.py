import re
from database import get_connection

SURFACES = {
    # HARD - ATP/WTA
    'Abu Dhabi WTA':'Hard','Adelaide':'Hard','Auckland':'Hard','Australian Open':'Hard',
    'Austin WTA':'Hard','Austin 2 WTA':'Hard','Austin 3 WTA':'Hard','Basel':'Hard',
    'Beijing':'Hard','Brisbane':'Hard','Canberra WTA':'Hard','Cancún WTA':'Hard',
    'Changsha WTA':'Hard','Chengdu':'Hard','Chennai WTA':'Hard','Cincinnati':'Hard',
    'Cincinnati WTA':'Hard','Cleveland WTA':'Hard','Cluj-Napoca 2 WTA':'Hard',
    'Colina WTA':'Hard','Dallas':'Hard','Delray Beach':'Hard','Doha':'Hard','Dubai':'Hard',
    'Florianopolis WTA':'Hard','Guangzhou':'Hard','Guadalajara WTA':'Hard',
    'Guadalajara 2 WTA':'Hard','Hangzhou':'Hard','Hobart':'Hard','Hong Kong ATP':'Hard',
    'Hong Kong WTA':'Hard','Indian Wells':'Hard','Jinan':'Hard','Jingshan':'Hard',
    'Jiujiang':'Hard','Los Cabos':'Hard','Manila':'Hard','Marseille':'Hard',
    'Masters Cup ATP':'Hard','Masters Cup WTA':'Hard','Metz':'Hard','Miami':'Hard',
    'Midland WTA':'Hard','Montpellier':'Hard','Montreal WTA':'Hard','Mumbai WTA':'Hard',
    'Newport Beach WTA':'Hard','Next Gen ATP Finals':'Hard','Ningbo WTA':'Hard',
    'Osaka WTA':'Hard','Ostrava 2 WTA':'Hard','Paris':'Hard','Paris WTA':'Hard',
    'Puerto Vallarta':'Hard','Queretaro':'Hard','Rotterdam':'Hard','Seoul WTA':'Hard',
    'Shanghai':'Hard','Singapore WTA':'Hard','Stockholm':'Hard','Suzhou':'Hard',
    'Tokyo':'Hard','Tokyo (Japan Open)':'Hard','Toronto':'Hard','US Open':'Hard',
    'Vienna':'Hard','Warsaw 2 WTA':'Hard','Washington':'Hard','Winston Salem':'Hard',
    'Wuhan':'Hard','Charleston':'Hard','Iasi WTA':'Hard','Montreal ITF':'Hard',

    # HARD - Challengers
    'Asuncion challenger':'Hard','Astana 5 challenger':'Hard','Augsburg challenger':'Hard',
    'Bangalore challenger':'Hard','Baton Rouge challenger':'Hard',
    'Bloomfield Hills challenger':'Hard','Brisbane challenger':'Hard',
    'Brisbane 3 challenger':'Hard','Brisbane 4 challenger':'Hard',
    'Canberra 2 challenger':'Hard','Cap Cana challenger':'Hard',
    'Champaign challenger':'Hard','Chennai challenger':'Hard','Cherbourg challenger':'Hard',
    'Chicago challenger':'Hard','Chisinau challenger':'Hard','Cleveland challenger':'Hard',
    'Columbus 3 challenger':'Hard','Drummondville challenger':'Hard',
    'Fairfield challenger':'Hard','Fujairah challenger':'Hard','Glasgow challenger':'Hard',
    'Granby challenger':'Hard','Guangzhou challenger':'Hard','Guangzhou 2 challenger':'Hard',
    'Helsinki challenger':'Hard','Islamabad challenger':'Hard','Istanbul challenger':'Hard',
    'Jinan challenger':'Hard','Jingshan challenger':'Hard','Kigali challenger':'Hard',
    'Kigali 2 challenger':'Hard','Knoxville challenger':'Hard','Kobe challenger':'Hard',
    'Koblenz challenger':'Hard','Las Vegas challenger':'Hard','Lexington challenger':'Hard',
    'Lille challenger':'Hard','Lincoln challenger':'Hard','Little Rock challenger':'Hard',
    'Lyon challenger':'Hard','Lyon 2 challenger':'Hard','Manama challenger':'Hard',
    'Manama 2 challenger':'Hard','Matsuyama challenger':'Hard','Milan challenger':'Hard',
    'New Delhi challenger':'Hard','Newport challenger':'Hard','Nonthaburi challenger':'Hard',
    'Nonthaburi 2 challenger':'Hard','Nonthaburi 3 challenger':'Hard',
    'Noumea challenger':'Hard','Orleans challenger':'Hard','Pau challenger':'Hard',
    'Phan Thiet challenger':'Hard','Phan Thiet 2 challenger':'Hard',
    'Phoenix challenger':'Hard','Playford 2 challenger':'Hard','Quimper challenger':'Hard',
    'San Diego challenger':'Hard','Seoul challenger':'Hard','Shanghai challenger':'Hard',
    'Shenzhen 2 challenger':'Hard','Sioux Falls challenger':'Hard',
    'Sydney challenger':'Hard','Taipei challenger':'Hard','Tampere challenger':'Hard',
    'Thionville challenger':'Hard','Tiburon challenger':'Hard','Winston Salem challenger':'Hard',
    'Wuxi challenger':'Hard','Yokkaichi challenger':'Hard','Yokohama challenger':'Hard',
    'Zhangjiagang challenger':'Hard',

    # HARD - ITF
    'Ahmedabad 2 ITF':'Hard','Ahmedabad ITF':'Hard','Alaminos-Larnaca ITF':'Hard',
    'Alaminos-Larnaca 2 ITF':'Hard','Alaminos-Larnaca 3 ITF':'Hard','Andong ITF':'Hard',
    'Bangalore ITF':'Hard','Birmingham ITF':'Hard','Brisbane 2 ITF':'Hard',
    'Brisbane 3 ITF':'Hard','Brisbane 4 ITF':'Hard','Brisbane 5 ITF':'Hard',
    'Brisbane ITF':'Hard','Burnie ITF':'Hard','Chihuahua 2 ITF':'Hard',
    'Chihuahua 3 ITF':'Hard','Chihuahua ITF':'Hard','Daegu ITF':'Hard',
    'Darwin 2 ITF':'Hard','Darwin ITF':'Hard','Dubai ITF':'Hard',
    'Fujairah ITF':'Hard','Fukui ITF':'Hard','Fukuoka ITF':'Hard',
    'Gifu ITF':'Hard','Goyang ITF':'Hard','Goyang 2 ITF':'Hard',
    'Gurugram ITF':'Hard','Gurugram 2 ITF':'Hard','Gurugram 3 ITF':'Hard',
    'Hamamatsu ITF':'Hard','Helsinki ITF':'Hard','Hongkong 9 ITF':'Hard',
    'Hong Kong ITF':'Hard','Hua Hin 6 ITF':'Hard','Hua Hin 7 ITF':'Hard',
    'Huzhou ITF':'Hard','Incheon ITF':'Hard','Istanbul ITF':'Hard',
    'Kalaburagi ITF':'Hard','Kashiwa ITF':'Hard','Kofu ITF':'Hard',
    'Kurume ITF':'Hard','Kyoto 2 ITF':'Hard','Launceston ITF':'Hard',
    'Luan ITF':'Hard','Luzhou ITF':'Hard','Maanshan ITF':'Hard',
    'Maanshan 2 ITF':'Hard','Makinohara ITF':'Hard','Mildura ITF':'Hard',
    'Nagpur ITF':'Hard','Nairobi ITF':'Hard','Nairobi 3 ITF':'Hard',
    'Nakhon Pathom ITF':'Hard','New Delhi ITF':'Hard','New Delhi 11 ITF':'Hard',
    'Nonthaburi ITF':'Hard','Nonthaburi 12 ITF':'Hard','Osaka 4 ITF':'Hard',
    'Palm Coast ITF':'Hard','Phan Thiet ITF':'Hard','Phan Thiet 2 ITF':'Hard',
    'Playford ITF':'Hard','Pune ITF':'Hard','Qian Daohu ITF':'Hard',
    'San Diego ITF':'Hard','San Diego 2 ITF':'Hard','San Diego 3 ITF':'Hard',
    'San Diego 4 ITF':'Hard','San Diego 5 ITF':'Hard','Sapporo ITF':'Hard',
    'Sapporo 2 ITF':'Hard','Shenzhen ITF':'Hard','Shenyang ITF':'Hard',
    'Singapore 5 ITF':'Hard','Singapore ITF':'Hard','Swan Hill ITF':'Hard',
    'Sydney 3 ITF':'Hard','Taipei 2 ITF':'Hard','Taipei 3 ITF':'Hard',
    'Taizhou ITF':'Hard','Takasaki ITF':'Hard','Tashkent ITF':'Hard',
    'Tashkent 2 ITF':'Hard','Tashkent 3 ITF':'Hard','Tashkent 4 ITF':'Hard',
    'Tauranga ITF':'Hard','Timaru ITF':'Hard','Tokyo 6 ITF':'Hard',
    'Toronto ITF':'Hard','Toyama ITF':'Hard','Tweed Heads ITF':'Hard',
    'Tweed Heads 2 ITF':'Hard','Wagga Wagga ITF':'Hard','Wagga Wagga 2 ITF':'Hard',
    'Wodonga ITF':'Hard','Yeongwol ITF':'Hard','Yeongwol 2 ITF':'Hard',
    'Yokohama ITF':'Hard','Guiyang ITF':'Hard','Hamilton (NZ) ITF':'Hard',
    'Manama ITF':'Hard',

    # CLAY - ATP/WTA
    'Acapulco':'Clay','Angers':'Clay','Athens':'Clay','Bastad':'Clay',
    'Bastad WTA':'Clay','Berlin':'Clay','Brussels':'Clay','Buenos Aires':'Clay',
    'Buenos Aires WTA':'Clay','Caldas da Rainha':'Clay','Cali':'Clay',
    'Contrexeville WTA':'Clay','Dubrovník':'Clay','French Open':'Clay',
    'Geneva':'Clay','Grado':'Clay','Gstaad':'Clay','Hamburg':'Clay',
    'Hamburg WTA':'Clay','Kitzbühel':'Clay','La Bisbal':'Clay',
    'Livesport Prague Open':'Clay','Ljubljana WTA':'Clay','Makarska':'Clay',
    'Mallorca':'Clay','Mallorca WTA':'Clay','Mérida':'Clay','Monterrey':'Clay',
    'Montreux WTA':'Clay','Palermo':'Clay','Parma':'Clay','Porto WTA':'Clay',
    'Quito WTA':'Clay','Rabat':'Clay','Rende':'Clay','Rio de Janeiro':'Clay',
    'Rio de Janeiro WTA':'Clay','Rome':'Clay','Rome WTA':'Clay','Rome 2 WTA':'Clay',
    'Rovereto':'Clay','Samsun':'Clay','Santiago':'Clay','Sao Paulo WTA':'Clay',
    'Strasbourg':'Clay','Tampico WTA':'Clay','Tolentino':'Clay','Tucuman':'Clay',
    'Umag':'Clay','Valencia WTA':'Clay','Vic':'Clay','Florianopolis challenger':'Clay',
    'San Sebastian WTA':'Clay','Almaty':'Hard','Angers':'Clay',

    # CLAY - Challengers
    'Aix en Provence challenger':'Clay','Alicante challenger':'Clay',
    'Antofagasta challenger':'Clay','Athens challenger':'Clay',
    'Bad Waltersdorf challenger':'Clay','Barranquilla chall.':'Clay',
    'Bergamo challenger':'Clay','Biella challenger':'Clay','Bogotá challenger':'Clay',
    'Bogotá 5 challenger':'Clay','Bonn challenger':'Clay','Bordeaux challenger':'Clay',
    'Braga challenger':'Clay','Brasilia challenger':'Clay','Brasília challenger':'Clay',
    'Brasov challenger':'Clay','Bratislava challenger':'Clay',
    'Bratislava 2 challenger':'Clay','Braunschweig challenger':'Clay',
    'Brest challenger':'Clay','Bucaramanga challenger':'Clay',
    'Buenos Aires challenger':'Clay','Buenos Aires 3 challenger':'Clay',
    'Bunschoten challenger':'Clay','Cali challenger':'Clay','Cancun challenger':'Clay',
    'Cary challenger':'Clay','Cassis challenger':'Clay','Cesenatico challenger':'Clay',
    'Charlottesville challenger':'Clay','Concepcion challenger':'Clay',
    'Cordoba challenger':'Clay','Cordenons challenger':'Clay',
    'Costa do Sauipe challenger':'Clay','Curitiba challenger':'Clay',
    'Estoril challenger':'Clay','Francavilla challenger':'Clay',
    'Genoa challenger':'Clay','Girona challenger':'Clay',
    'Grodzisk Mazowiecki challenger':'Clay','Guayaquil challenger':'Clay',
    'Hamburg challenger':'Clay','Heilbronn challenger':'Clay',
    'Hersonissos challenger':'Clay','Hersonissos 2 challenger':'Clay',
    'Hersonissos 3 challenger':'Clay','Hersonissos 4 challenger':'Clay',
    'Hersonissos 5 challenger':'Clay','Hersonissos 6 challenger':'Clay',
    'Iasi challenger':'Clay','Itajai challenger':'Clay','Lima challenger':'Clay',
    'Lima 2 challenger':'Clay','Lima 3 challenger':'Clay','Lisbon challenger':'Clay',
    'Lugano challenger':'Clay','Luedenscheid challenger':'Clay','Maia challenger':'Clay',
    'Mallorca challenger':'Clay','Merida challenger':'Clay','Metepec challenger':'Clay',
    'Monastir challenger':'Clay','Montemar challenger':'Clay',
    'Montevideo challenger':'Clay','Morelia challenger':'Clay',
    'Morelos challenger':'Clay','Mouilleron-Le-Captif challenger':'Clay',
    'Murcia challenger':'Clay','Neapol challenger':'Clay','Olbia challenger':'Clay',
    'Perugia challenger':'Clay','Piracicaba challenger':'Clay',
    'Porto challenger':'Clay','Porto 2 challenger':'Clay',
    'Porto Alegre challenger':'Clay','Poznan challenger':'Clay',
    'Pozoblanco challenger':'Clay','Prague 2 challenger':'Clay',
    'Prostejov challenger':'Clay','Punta del Este 2 challenger':'Clay',
    'Pune challenger':'Clay','Rennes challenger':'Clay','Roanne challenger':'Clay',
    'Rosario challenger':'Clay','Royan challenger':'Clay',
    'Saint Brieuc challenger':'Clay','San Marino challenger':'Clay',
    'San Miguel de Tucuman challenger':'Clay','Santa Fe challenger':'Clay',
    'Santiago challenger':'Clay','Santos challenger':'Clay',
    'Sao Paulo 2 challenger':'Clay','Sassuolo challenger':'Clay',
    'Segovia challenger':'Clay','Sevilla challenger':'Clay','Skopje challenger':'Clay',
    'Sofia challenger':'Clay','Sofia 3 challenger':'Clay','Soma Bay challenger':'Clay',
    'Split challenger':'Clay','St. Tropez challenger':'Clay','Sumter challenger':'Clay',
    'Targu Mures challenger':'Clay','Targu Mures 2 challenger':'Clay',
    'Tbilisi challenger':'Clay','Temuco challenger':'Clay','Tenerife challenger':'Clay',
    'Tenerife 2 challenger':'Clay','Tigre challenger':'Clay','Tigre 2 challenger':'Clay',
    'Todi challenger':'Clay','Troyes challenger':'Clay','Tulln challenger':'Clay',
    'Tunis challenger':'Clay','Turin challenger':'Clay','Tyler challenger':'Clay',
    'Valencie challenger':'Clay','Vicenza challenger':'Clay',
    'Villa Maria challenger':'Clay','Villena challenger':'Clay',
    'Zadar challenger':'Clay','Zagreb challenger':'Clay','Zug challenger':'Clay',
    'Granby ITF':'Clay','Granby challenger':'Clay',

    # CLAY - ITF
    'Alcala de Henares ITF':'Clay','Aldershot ITF':'Clay','Alkmaar ITF':'Clay',
    'Amstelveen ITF':'Clay','Amstetten ITF':'Clay','Andrezieux-Boutheon ITF':'Clay',
    'Ankara 2 ITF':'Clay','Ankara 3 ITF':'Clay','Arcadia ITF':'Clay',
    'Aschaffenburg ITF':'Clay','Austin ITF':'Clay','Banja Luka ITF':'Clay',
    'Bastad ITF':'Clay','Baza ITF':'Clay','Bellinzona ITF':'Clay',
    'Bethany Beach ITF':'Clay','Biarritz ITF':'Clay','Bielsko Biala ITF':'Clay',
    'Bissy-Chambéry ITF':'Clay','Bistrita ITF':'Clay','Blois ITF':'Clay',
    'Boca Raton 5 ITF':'Clay','Boca Raton 6 ITF':'Clay','Boca Raton ITF':'Clay',
    'Bolszewo ITF':'Clay','Bonita Springs ITF':'Clay','Bradenton ITF':'Clay',
    'Brasov 2 ITF':'Clay','Brasov 3 ITF':'Clay','Bratislava 6 ITF':'Clay',
    'Brescia ITF':'Clay','Bucharest 2 ITF':'Clay','Bucharest 3 ITF':'Clay',
    'Bucharest 4 ITF':'Clay','Bucharest 6 ITF':'Clay','Bucharest 7 ITF':'Clay',
    'Bucharest 9 ITF':'Clay','Bucharest 10 ITF':'Clay','Buenos Aires 2 ITF':'Clay',
    'Buenos Aires 3 ITF':'Clay','Buenos Aires ITF':'Clay','Buzau ITF':'Clay',
    'Bydgoszcz ITF':'Clay','Bytom ITF':'Clay','Campina ITF':'Clay',
    'Campulung ITF':'Clay','Cary ITF':'Clay','Casablanca 2 ITF':'Clay',
    'Casablanca ITF':'Clay','Caserta ITF':'Clay','Castellon 2 ITF':'Clay',
    'Castellon ITF':'Clay','Cayenne ITF':'Clay','Ceska Lipa ITF':'Clay',
    'Ceuta ITF':'Clay','Chacabuco ITF':'Clay','Changwon ITF':'Clay',
    'Cherbourg-en-Cotentin ITF':'Clay','Cluj-Napoca ITF':'Clay',
    'Cordenons 2 ITF':'Clay','Corroios-Seixal ITF':'Clay','Criciuma ITF':'Clay',
    'Croissy-Beaubourg ITF':'Clay','Cuiabá ITF':'Clay','Darmstadt ITF':'Clay',
    'Daytona Beach ITF':'Clay','Decatur ITF':'Clay','Denia ITF':'Clay',
    'Dijon 2 ITF':'Clay','Dinard ITF':'Clay','Don Benito ITF':'Clay',
    'Dublin ITF':'Clay','Edgbaston ITF':'Clay','Edmond ITF':'Clay',
    'Erwitte ITF':'Clay','Essen ITF':'Clay','Estepona ITF':'Clay',
    'Evansville ITF':'Clay','Evora ITF':'Clay','Faro ITF':'Clay',
    'Fiano Romano ITF':'Clay','Figueira Da Foz ITF':'Clay',
    'Florence (USA) ITF':'Clay','Focsani ITF':'Clay','Funchal ITF':'Clay',
    'Galati ITF':'Clay','Gdansk ITF':'Clay','Getxo ITF':'Clay',
    'Glasgow 2 ITF':'Clay','Glasgow ITF':'Clay','Gonesse ITF':'Clay',
    'Gran Canaria ITF':'Clay','Grenoble ITF':'Clay',
    'Grodzisk Mazowiecki ITF':'Clay','Guimaraes ITF':'Clay','Haag 2 ITF':'Clay',
    'Haag 3 ITF':'Clay','Hagetmau ITF':'Clay','Haren ITF':'Clay',
    'Hechingen ITF':'Clay','Heraklion ITF':'Clay','Herrenschwanden ITF':'Clay',
    'Hillcrest ITF':'Clay','Hillcrest 2 ITF':'Clay','Hillcrest 3 ITF':'Clay',
    'Hilton Head Island ITF':'Clay','Horb ITF':'Clay','Huamantla ITF':'Clay',
    'Huamantla 2 ITF':'Clay','Huamantla 3 ITF':'Clay','Huamantla 4 ITF':'Clay',
    'Huntsville ITF':'Clay','Hurghada ITF':'Clay','Hurghada 2 ITF':'Clay',
    'Hurghada 3 ITF':'Clay','Ibague ITF':'Clay',
    'Indian Harbour Beach ITF':'Clay','Irapuato ITF':'Clay','Junin ITF':'Clay',
    'Kalmar ITF':'Clay','Kaltenkirchen ITF':'Clay','Kamen ITF':'Clay',
    'Klagenfurt ITF':'Clay','Klosters ITF':'Clay','Knokke ITF':'Clay',
    'Koksijde ITF':'Clay','Koper ITF':'Clay','Kotka ITF':'Clay',
    'Kraków ITF':'Clay','Krsko ITF':'Clay','Kunshan ITF':'Clay',
    'Lagos (Port.) ITF':'Clay','Lakewood ITF':'Clay','Landisville 2 ITF':'Clay',
    'Las Vegas 2 ITF':'Clay','Le Havre ITF':'Clay','Le Lamentin ITF':'Clay',
    'Le Neubourg ITF':'Clay','Leimen ITF':'Clay','Leipzig ITF':'Clay',
    'Leiria ITF':'Clay','Leme ITF':'Clay','Leszno ITF':'Clay',
    'Lexington ITF':'Clay','Liberec ITF':'Clay','Lima 11 ITF':'Clay',
    'Lima 13 ITF':'Clay','Lima 14 ITF':'Clay','Lincoln ITF':'Clay',
    'Lisbon ITF':'Clay','Logrono ITF':'Clay','Lopota 2 ITF':'Clay',
    'Los Angeles ITF':'Clay','Loule ITF':'Clay','Lousada ITF':'Clay',
    'Lousada 2 ITF':'Clay','Lujan ITF':'Clay','Lujan 2 ITF':'Clay',
    'Macon ITF':'Clay','Macon 2 ITF':'Clay','Madrid ITF':'Clay',
    'Madrid 2 ITF':'Clay','Malta ITF':'Clay','Manacor ITF':'Clay',
    'Manacor 2 ITF':'Clay','Manacor 3 ITF':'Clay','Manchester ITF':'Clay',
    'Maribor ITF':'Clay','Maspalomas ITF':'Clay','Melilla ITF':'Clay',
    'Merzig ITF':'Clay','Mogi Das Cruzes ITF':'Clay','Mogyorod ITF':'Clay',
    'Mohammedia ITF':'Clay','Montemor-O-Novo ITF':'Clay','Monzon ITF':'Clay',
    'Murska Sobota ITF':'Clay','Naples 4 ITF':'Clay','Neuquén ITF':'Clay',
    'Neuquén 2 ITF':'Clay','Nogent-sur-Marne ITF':'Clay','Norman ITF':'Clay',
    'Norges-la-Ville ITF':'Clay','Nules ITF':'Clay','Oegstgeest ITF':'Clay',
    'Oldenzaal ITF':'Clay','Olomouc ITF':'Clay','Orlando 3 ITF':'Clay',
    'Orlando 4 ITF':'Clay','Orlando 6 ITF':'Clay','Orlando 7 ITF':'Clay',
    'Ortisei ITF':'Clay','Osijek ITF':'Clay','Oslo ITF':'Clay',
    'Otocec ITF':'Clay','Otopeni ITF':'Clay','Ourense ITF':'Clay',
    'Palma del Rio ITF':'Clay','Pazardzhik ITF':'Clay','Pazardzhik 2 ITF':'Clay',
    'Pelham ITF':'Clay','Pergamino ITF':'Clay','Perigueux ITF':'Clay',
    'Petange 2 ITF':'Clay','Platja D\'Aro ITF':'Clay','Poitiers ITF':'Clay',
    'Porto 4 ITF':'Clay','Porto 5 ITF':'Clay','Porto 6 ITF':'Clay',
    'Prague 2 ITF':'Clay','Prague 6 ITF':'Clay','Quebec City ITF':'Clay',
    'Quinta do Lago ITF':'Clay','Radom ITF':'Clay',
    'Rancho Santa Fe ITF':'Clay','Rancho Santa Fe 2 ITF':'Clay',
    'Redding ITF':'Clay','Reims ITF':'Clay','Reus ITF':'Clay',
    'Ribeirao Preto ITF':'Clay','Rio Claro ITF':'Clay','Roehampton ITF':'Clay',
    'Roehampton 2 ITF':'Clay','Rogaska Slatina ITF':'Clay','Rome 2 ITF':'Clay',
    'Sabadell ITF':'Clay','Saguenay ITF':'Clay',
    'Saint Palais sur Mer ITF':'Clay','Saint-Gaudens ITF':'Clay',
    'San Gregorio ITF':'Clay','San Gregorio 2 ITF':'Clay',
    'San Rafael ITF':'Clay','Santiago ITF':'Clay','Santiago 5 ITF':'Clay',
    'Santiago 6 ITF':'Clay','Santiago 7 ITF':'Clay',
    'Santo Domingo 3 ITF':'Clay','Santo Domingo 4 ITF':'Clay',
    'Santo Domingo 5 ITF':'Clay','Santo Domingo 6 ITF':'Clay',
    'Santo Domingo 8 ITF':'Clay','Santo Domingo 9 ITF':'Clay',
    'Sao Joao da Boa Vista ITF':'Clay','Sao Luis do Maranhao ITF':'Clay',
    'Sao Paulo 3 ITF':'Clay','Sao Paulo 4 ITF':'Clay','Sao Paulo 6 ITF':'Clay',
    'Saskatoon ITF':'Clay','Savitaipale ITF':'Clay','Selva Gardena ITF':'Clay',
    'Sevilla ITF':'Clay','Sheffield ITF':'Clay','Sibenik ITF':'Clay',
    'Slobozia ITF':'Clay','Slovenske Konjice ITF':'Clay','Solapur ITF':'Clay',
    'Solarino ITF':'Clay','Solarino 2 ITF':'Clay','Solarino 5 ITF':'Clay',
    'Southaven ITF':'Clay','Spring ITF':'Clay','Sumter ITF':'Clay',
    'Sumter 2 ITF':'Clay','Sunderland ITF':'Clay','Szabolcsveresmart ITF':'Clay',
    'Szekesfehervar ITF':'Clay','Taby ITF':'Clay','Targu Mures ITF':'Clay',
    'Tarvisio ITF':'Clay','Tauste-Zaragoza ITF':'Clay','Telavi 7 ITF':'Clay',
    'Telavi 8 ITF':'Clay','Templeton ITF':'Clay','Terrassa ITF':'Clay',
    'Torello ITF':'Clay','Trieste ITF':'Clay','Trnava ITF':'Clay',
    'Trnava 2 ITF':'Clay','Trnava 5 ITF':'Clay','Trnava 6 ITF':'Clay',
    'Trnava 8 ITF':'Clay','Troisdorf ITF':'Clay','Tsaghkadzor ITF':'Clay',
    'Tsaghkadzor 2 ITF':'Clay','Turin ITF':'Clay','Tyler ITF':'Clay',
    'Uvero Alto ITF':'Clay','Uvero Alto 2 ITF':'Clay','Vaihingen ITF':'Clay',
    'Varna ITF':'Clay','Verbier ITF':'Clay','Verbier 2 ITF':'Clay',
    'Victoriaville ITF':'Clay','Vigo ITF':'Clay','Villena ITF':'Clay',
    'Wanfercee-Baulet ITF':'Clay','Warmbad-Villach ITF':'Clay',
    'Weston ITF':'Clay','Wichita ITF':'Clay','Wrexham ITF':'Clay',
    'Yecla ITF':'Clay','Ystad ITF':'Clay','Zagreb 2 ITF':'Clay',
    'Zagreb ITF':'Clay','Zaragoza ITF':'Clay',

    # HARD - manquants
    'Bakersfield ITF':'Hard',       # Californie, surface dure
    'Berkeley ITF':'Hard',          # Californie, surface dure
    'Bari WTA':'Hard',              # Italie, surface dure
    'Hamburg 2 ITF':'Hard',         # ITF Hamburg, surface dure (indoor)
    'Hameenlinna ITF':'Hard',       # Finlande, indoor hard
    'Kayseri ITF':'Hard',           # Turquie, surface dure
    'Suzhou challenger':'Hard',     # Chine, surface dure
    'Winnipeg challenger':'Hard',   # Canada, indoor hard

    # CLAY - manquants
    "Cap d'Agde ITF":'Clay',        # France, terre battue
    'Clemson ITF':'Clay',           # USA, terre battue (Clemson est sur clay)
    'Como challenger':'Clay',       # Italie, terre battue
    'Les Franqueses ITF':'Clay',    # Espagne, terre battue
    "Les Sables d'Olonne":'Clay',   # France, terre battue
    'Liberec challenger':'Clay',    # Rép. tchèque, terre battue
    'Limoges':'Clay',               # France, terre battue
    'Modena challenger':'Clay',     # Italie, terre battue
    'Santa Tecla ITF':'Clay',       # Espagne, terre battue
    'Santa Tecla 2 ITF':'Clay',     # Espagne, terre battue
    'Szczecin challenger':'Clay',   # Pologne, terre battue
    'Trelew ITF':'Clay',            # Argentine, terre battue
    'Trelew 2 ITF':'Clay',          # Argentine, terre battue
    'Trieste challenger':'Clay',    # Italie, terre battue
    "Villeneuve d'Ascq ITF":'Clay', # France, terre battue
    'Viserba ITF':'Clay',           # Italie, terre battue
    'Vitoria-Gasteiz ITF':'Clay',   # Espagne, terre battue
    'Vídeň ITF':'Clay',             # Vienne, terre battue

    # GRASS - manquants
    'Halle':'Grass',                # ATP Halle, gazon (Wimbledon prep)

    # GRASS
    'Bad Homburg WTA':'Grass','Birmingham':'Grass','Birmingham challenger':'Grass',
    'Eastbourne':'Grass','Hertogenbosch':'Grass','Ilkley WTA':'Grass',
    'Ilkley challenger':'Grass','Nottingham':'Grass',
    'Nottingham 3 challenger':'Grass','Nottingham 5 challenger':'Grass',
    'Nottingham challenger':'Grass',"Queen's Club":'Grass','Wimbledon':'Grass',
    'Nottingham 3 ITF':'Grass','Nottingham 6 ITF':'Grass','Nottingham 7 ITF':'Grass',

    # EXCLUS
    'A Racquet at The Rock':'Unknown','Atlanta - exhibition':'Unknown',
    'Austrian Bundesliga':'Unknown','Billie Jean King Cup':'Unknown',
    'Boodles Tennis Challenge':'Unknown','Bundesliga - men':'Unknown',
    'Bundesliga - women':'Unknown','Charlotte Invitational':'Unknown',
    'Czech league':'Unknown','Davis Cup':'Unknown',
    'France - Championship':'Unknown','Hopman Cup':'Unknown',
    # Futures couverts par pattern r'^Futures \d{4}$' → pas besoin d'entrées statiques
    'Hurlingham - exhibition':'Unknown','Incheon - exhibition':'Unknown',
    'Kooyong - exh.':'Unknown','Las Vegas - exhibition':'Unknown',
    'Laver Cup':'Unknown','Macau - exhibition':'Unknown',
    'Miami Invitational':'Unknown','Next Gen ATP Finals':'Hard',
    'Shenzhen - exhibition':'Unknown','Six Kings Slam':'Unknown',
    'Swiss Nationalliga A':'Unknown','The Garden Cup':'Unknown',
    'United Cup':'Unknown','UTR Pro Match Series':'Unknown',
    'UTR Pro Match Series 2':'Unknown','UTR Pro Tennis Series':'Unknown',
    'UTR Pro Tennis Series 3':'Unknown','UTR Pro Tennis Series 5':'Unknown',
    'UTR Pro Tennis Series 6':'Unknown','UTR Pro Tennis Series 8':'Unknown',
    'UTR Pro Tennis Series 9':'Unknown','Ultimate Tennis Showdown':'Unknown',
    'World Tennis League':'Unknown','World University Games':'Unknown',
}

PATTERNS = [
    # Futures : exclus quel que soit l'année (Futures 2024, 2025, 2026, ...)
    (r'^Futures \d{4}$',                    'Unknown'),

    (r'^Antalya \d+ ITF$',                  'Hard'),
    (r'^Astana \d+ ITF$',                   'Hard'),
    (r'^Bol \d+ ITF$',                      'Clay'),
    (r'^Heraklion \d+ ITF$',               'Clay'),
    (r'^Kayseri \d+ ITF$',                  'Hard'),
    (r'^Kursumlijska Banja \d+ ITF$',       'Clay'),
    (r'^Lima \d+ ITF$',                     'Clay'),
    (r'^Luan \d+ ITF$',                     'Hard'),
    (r'^Maanshan \d+ ITF$',                 'Hard'),
    (r'^Monastir \d+ ITF$',                 'Clay'),
    (r'^Nakhon Pathom \d+ ITF$',            'Hard'),
    (r'^Nonthaburi \d+ ITF$',               'Hard'),
    (r'^Santa Margherita Di Pula \d+ ITF$', 'Clay'),
    (r'^Sharm El Sheikh \d+ ITF$',          'Clay'),
    (r'^Solarino \d+ ITF$',                 'Clay'),
    (r'^Trnava \d+ ITF$',                   'Clay'),
]


def apply_pattern(name):
    for pattern, surface in PATTERNS:
        if re.match(pattern, name):
            return surface
    return None


if __name__ == "__main__":
    conn = get_connection()
    try:
        c = conn.cursor()

        updated = 0
        for name, surface in SURFACES.items():
            c.execute("""
                INSERT INTO tournament_surfaces (name, surface)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET surface = excluded.surface
            """, (name, surface))
            updated += 1

        c.execute("SELECT name FROM tournament_surfaces WHERE surface = 'Unknown'")
        still_unknown = [r[0] for r in c.fetchall()]
        pattern_updated = 0
        for name in still_unknown:
            surface = apply_pattern(name)
            if surface:
                c.execute("UPDATE tournament_surfaces SET surface = ? WHERE name = ?",
                          (surface, name))
                pattern_updated += 1

        conn.commit()
        print(f"✅ {updated} tournois mappés via dict.")
        print(f"✅ {pattern_updated} tournois mappés via patterns.")

        c.execute("SELECT name FROM tournament_surfaces WHERE surface = 'Unknown' ORDER BY name")
        remaining = [r[0] for r in c.fetchall()]
        excluded_kw = ['utr','futures','davis','billie','united cup','exhibition',
                       'showdown','bundesliga','league','laver','hopman','kooyong',
                       'macau','six kings','world tennis','university','miami inv',
                       'garden cup','racquet at','charlotte inv','swiss national',
                       'boodles','france - championship']
        real_unknown = [t for t in remaining
                        if not any(k in t.lower() for k in excluded_kw)]

        if real_unknown:
            print(f"\n⚠️  {len(real_unknown)} tournois vraiment inconnus :")
            for t in real_unknown:
                print(f"   ❓ {t}")
            print(f"\n💡 Lance : py set_surface.py 'Nom tournoi' Clay|Hard|Grass")
        else:
            print(f"\n🎉 Plus aucun tournoi inconnu ! ({len(remaining)} exclus volontairement)")
    finally:
        conn.close()