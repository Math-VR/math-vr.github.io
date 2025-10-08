
// Data file (adapted for data_new)

BASE_DIR = ""; // not used for new data, image paths are absolute/relative already

DATA_FILE = "data_new/data_public.js";


// Variables for the filters with the number of questions
let number_options = [5, 10, 20];  
let categories = ["All"]; // will be populated from data_new on load

// Elements in the Option Panel
let optbtn = document.getElementsByClassName("optionsbtn")[0];
let closebtn = document.getElementsByClassName("closebtn")[0];
let optionpanel = document.getElementById("option-panel");
let optboxes = document.getElementsByClassName("optbox");
let opt_dds = document.getElementsByClassName("opt-dd");
let filter_submit = document.getElementById("filter-submit");

// Element Text the Option Panel
let number_dd = make_dropdown("How many samples?", number_options, "number_dd");
let category_dd = make_dropdown("Choose a category:", categories, "category_dd");

// Content in the Option Box
optboxes[0].innerHTML += number_dd;
optboxes[0].innerHTML += category_dd;

// Elements in the Content Body
let body = document.getElementById("content-body");
let display = document.getElementById("display");

// Click actions for the option buttons
optbtn.addEventListener("click", openNav);
closebtn.addEventListener("click", closeNav);

// 单列布局，不需要复杂的响应式调整
// 内容将垂直排列，充分利用宽度

// Set up the data filters and display the page
let filters = {};

// Auto refresh when dropdowns change
document.addEventListener("DOMContentLoaded", () => {
    const numberDd = document.getElementById("number_dd");
    const catDd = document.getElementById("category_dd");
    
    if (numberDd) {
        numberDd.addEventListener("change", () => { 
            change_filters(); 
            filter_data(); 
        });
    }
    
    if (catDd) {
        catDd.addEventListener("change", () => { 
            change_filters(); 
            filter_data(); 
        });
    }
    
    // Initialize filters and load data
    change_filters();
    filter_data();
});

// Display the page when clicking the fresh button
filter_submit.addEventListener("click", () => {
    filter_data();
    // 确保数学公式重新渲染
    setTimeout(() => {
        if (window.MathJax && window.MathJax.typesetPromise) {
            MathJax.typesetPromise().then(() => {
                console.log("MathJax rendering completed after refresh");
            }).catch((err) => {
                console.log("MathJax rendering error after refresh:", err);
            });
        }
    }, 100);
});

if (window.innerWidth < 600) {
    filter_submit.addEventListener("click", closeNav);
}

// Display the page when it is running at the first time
filter_data();

// Functions
var display_padding = display.style.padding;
function openNav() {
    if (window.innerWidth < 600) {
        // optionpanel.style.zIndex = "2";
        optionpanel.style.width = "100vw";
        display.style.width = "0vw";
        display.style.padding = "0";
    } else {
        optionpanel.style.width = "25vw";
        display.style.width = "70vw";
    }
    for (each of optionpanel.children) 
        each.style.display = "block";
}

function closeNav() {
    // display.style.display = "block";
    optionpanel.style.width = "0vw";
    display.style.width = "100vw";
    display
    for (each of optionpanel.children) {
        each.style.display = "none";
    }
}

// Function: update the filter values
function change_filters(e) {
    const numberDd = document.getElementById("number_dd");
    const catDd = document.getElementById("category_dd");
    
    if (numberDd) {
        filters.number = parseInt(numberDd.value);
    }
    if (catDd) {
        filters.category = catDd.value;
    }
    
    console.log("Filters updated:", filters);
}

// Function: draw the page
function create_page(d) {
    if (d.length === 0) {
        body.innerHTML = "<p>No number satisfies All the filters.</p>";
    } else {
        // 改为一列布局，所有内容垂直排列
        body.innerHTML = create_col(d);
    }
    reflow(body);
    console.log("reflowed");
}

function create_col(data) {
    res = [];

    for (each of data) {
        res.push(create_number(each));
    }

    return `<div class="display-col"> ${res.join("")} </div>`;
}

// data is an object with the following attr.
function create_number(data) {
    let question = make_qt(data.pid, data.question, null);

    let cat = data.category ? `<p class="meta-txt">Category: ${data.category}</p>` : "";
    
    // 添加 analysis 部分
    let analysis = "";
    if (data.analysis) {
        analysis = `<p><b>Analysis</b></p><p class="analysis-txt">${data.analysis}</p>`;
    }

    html = make_box([question, analysis, cat]) + "<hr/>";

    return html;
}

// creates a div with question text in it
function make_qt(pid, question, unit) {
    let html = "";
    html = `
                <p><b>Question </b></p>
                <div class="question-txt">[No.${pid}] ${question}</div>
        `;
    return html;
}

function make_hint(hint) {
    if (hint === null) return "";
    let html = `<p><b>Context </b></p><p class="hint-txt">${hint}</p>`;
    return html;
}

function make_img(path) {
    if (path === null) return "";
    let html = `<img src="${path}" alt="number image" class="question-img" />`;
    return html;
}

function make_box(contents, cls = "") {
    if (contents.join("").length === 0) return "";
    let html = `
        <div class="box ${cls}"> 
            ${contents.join(" ")}
        </div>
    `;
    return html;
}

function make_choices(choices) {
    // console.log(choices);
    let temp = "";
    let len = 0;
    for (each of choices) {
        let html = make_choice(each);
        temp += html;
        len += each.length;
    }
    let html = "";
    if (len < 60)
        html = `<p><b>Choices </b></p><div class="choices">${temp}</div>`;
    else
        html = `<p><b>Choices </b></p><div class="choices-vertical">${temp}</div>`;
    return html;
}
function make_choice(choice) {
    let html = `<p class="choice-txt">${choice}</p>`;
    return html;
}

function make_answer(answer) {
    let html = `<p><b>Answer </b></p><p class="answer-txt">${answer}</p>`;
    return html;
}

function make_dropdown(label, options, id, default_ind = 0) {
    let html = "";
    for (let i = 0; i < options.length; i++) {
        if (i === default_ind)
            html += `<option value="${options[i]}" selected> ${options[i]} </option>`;
        else
            html += `<option value="${options[i]}"> ${options[i]} </option>`;
    }
    html = `<label class="dd-label">${label} <select id="${id}" class="opt-dd"> ${html} </select> </label><br/>`;
    return html;
}


// Main Functions (FIXME: need to be updated)
async function filter_data() {
    // set up or update the filter
    change_filters();

    console.log(filters);
    // e.g. data/{"dataset": "CLEVR-Math", "number": 20}

    // success event 
    let scriptEle = document.createElement("script");
    scriptEle.setAttribute("src", `${DATA_FILE}`);
    scriptEle.setAttribute("type", "text/javascript");
    scriptEle.setAttribute("async", false);
    document.body.appendChild(scriptEle);

    scriptEle.addEventListener("load", () => {
        console.log("File loaded");
        res = test_data;
        // console.log(res);


        // go over res and add pid to each element
        for (let i of Object.keys(res)) {
            res[i].pid = i;
        }


        // populate categories dynamically
        let catSet = new Set(["All"]);
        for (let k of Object.keys(res)) {
            if (res[k].category) catSet.add(res[k].category.toString());
        }
        let catArr = Array.from(catSet);
        let catSelect = document.getElementById("category_dd");
        if (catSelect) {
            const prevVal = catSelect.value || "All";
            const selected = catArr.includes(prevVal) ? prevVal : "All";
            catSelect.innerHTML = catArr.map((c)=>`<option value="${c}" ${c===selected?"selected":""}> ${c} </option>`).join("");
        }

        // filter: category (strict by normalized text)
        const selectedCatRaw = document.getElementById("category_dd").value || "All";
        const selectedCat = selectedCatRaw.toString().trim().toLowerCase();
        if (selectedCat !== "all") {
            for (let i of Object.keys(res)) {
                const itemCat = (res[i].category||"").toString().trim().toLowerCase();
                if (itemCat !== selectedCat) {
                    delete res[i];
                }
            }
        }


        // filter: number
        cnt = filters.number;
        if (cnt && cnt !== "All") {
            cnt = Number.parseInt(cnt);
            d = _.sample(Object.values(res), Math.min(cnt, Object.keys(res).length));
        } else {
            d = Object.values(res);
        }

   
        create_page(d);
        
        // 重新渲染数学公式
        if (window.MathJax && window.MathJax.typesetPromise) {
            MathJax.typesetPromise().then(() => {
                console.log("MathJax rendering completed");
            }).catch((err) => {
                console.log("MathJax rendering error:", err);
            });
        }
    });
}

// force the browser to reflow
function reflow(elt) {
    elt.offsetHeight;
}
