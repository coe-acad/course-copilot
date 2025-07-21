import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyD0Sw4N-qXV2NEsL7dR89yTrCsjhxmLh-c",
  authDomain: "creators-copilot.firebaseapp.com",
  databaseURL: "https://creators-copilot-default-rtdb.firebaseio.com",
  projectId: "creators-copilot",
  storageBucket: "creators-copilot.firebasestorage.app",
  messagingSenderId: "919304587005",
  appId: "1:919304587005:web:7bb39bdf8e878588196094",
  measurementId: "G-WFWZ9TYJVX"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app); 